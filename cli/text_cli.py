"""CLI commands for the Text system: pwd, print, add, rm, up, cd, plus
save/load for persistence (Data layer)."""

from __future__ import annotations

from core.text import (
    ContainerElement,
    DocumentConverter,
    ElementKind,
    Heading,
    Image,
    Link,
    Paragraph,
    PrototypeRegistry,
    Root,
    TextElement,
    TextFactory,
    factory_for,
)
from core.text.visitor import TextElementVisitor
from data import Repository

from .framework import Args, Command, FunctionCommand, ICommandStrategy


class _ElementKindVisitor(TextElementVisitor[ElementKind]):
    """Visitor: maps an element to its ElementKind by the role it plays,
    so Markdown/HTML variants and future subclasses are handled too."""

    def visit_root(self, root: Root) -> ElementKind:
        raise TypeError("The document root has no element kind")

    def visit_heading(self, heading: Heading) -> ElementKind:
        return ElementKind.HEADING

    def visit_paragraph(self, paragraph: Paragraph) -> ElementKind:
        return ElementKind.PARAGRAPH

    def visit_link(self, link: Link) -> ElementKind:
        return ElementKind.LINK

    def visit_image(self, image: Image) -> ElementKind:
        return ElementKind.IMAGE


_KIND_OF = _ElementKindVisitor()


class TextNavigator:
    def __init__(self) -> None:
        self.factory = TextFactory()
        self.root: Root = self.factory.create_document()
        self.cursor: ContainerElement = self.root
        self._ids: dict[int, str] = {}
        self._by_id: dict[str, TextElement] = {}
        self._counters: dict[str, int] = {}

    def _assign_id(self, element: TextElement, kind: ElementKind) -> str:
        prefix = {ElementKind.HEADING: "h", ElementKind.PARAGRAPH: "p",
                  ElementKind.LINK: "l", ElementKind.IMAGE: "i"}[kind]
        self._counters[prefix] = self._counters.get(prefix, 0) + 1
        display_id = f"{prefix}{self._counters[prefix]}"
        self._ids[id(element)] = display_id
        self._by_id[display_id] = element
        return display_id

    def display_id(self, element: TextElement) -> str:
        return self._ids.get(id(element), "?")

    def find_by_id(self, display_id: str) -> TextElement | None:
        return self._by_id.get(display_id)

    def label(self, element: TextElement) -> str:
        if isinstance(element, Root):
            return "/"
        if isinstance(element, Heading):
            return element.title
        return f"<{self.display_id(element)}>"

    def create_and_attach(self, kind: ElementKind, **fields: str) -> TextElement:
        element = self.factory.create(kind, **fields)
        self.cursor.add(element)
        self._assign_id(element, kind)
        return element

    def pwd(self) -> str:
        segments: list[str] = []
        node: ContainerElement | None = self.cursor
        while node is not None and not isinstance(node, Root):
            segments.append(self.label(node))
            node = node.parent
        return "/" + "/".join(reversed(segments))

    def go_up(self) -> bool:
        if self.cursor.parent is None:
            return False
        self.cursor = self.cursor.parent
        return True

    def go_to_id(self, display_id: str) -> bool:
        target = self.find_by_id(display_id)
        if not isinstance(target, ContainerElement):
            return False
        self.cursor = target
        return True

    def go_to_path(self, path: str) -> bool:
        node: ContainerElement = self.root if path.startswith("/") else self.cursor
        segments = [segment for segment in path.split("/") if segment]
        for segment in segments:
            match = next(
                (child for child in node.children
                 if isinstance(child, ContainerElement) and self.label(child) == segment),
                None,
            )
            if match is None:
                return False
            node = match
        self.cursor = node
        return True

    def find_child_by_name(self, name: str) -> TextElement | None:
        for child in self.cursor.children:
            if self.label(child) == name or self.display_id(child) == name:
                return child
        return None

    def replace_document(self, new_root: Root) -> None:
        self.root = new_root
        self.cursor = new_root
        self._ids.clear()
        self._by_id.clear()
        self._counters.clear()
        self._reassign_ids(new_root)

    def _reassign_ids(self, container: ContainerElement) -> None:
        # Iterator: one flat loop over the whole subtree, no recursion.
        for element, _ in container.walk():
            self._assign_id(element, element.accept(_KIND_OF))

    def register_subtree(self, element: TextElement) -> None:
        """Gives ids to an element added from outside (a clone, a loaded
        document) and to everything inside it."""
        self._assign_id(element, element.accept(_KIND_OF))
        if isinstance(element, ContainerElement):
            self._reassign_ids(element)

    def attach(self, element: TextElement) -> None:
        self.cursor.add(element)
        self.register_subtree(element)


def _cmd_pwd(nav: TextNavigator, ctx: Args) -> None:
    print(nav.pwd())


def _cmd_print(nav: TextNavigator, ctx: Args) -> None:
    format_name = ctx.option("format")
    if format_name:
        # Abstract Factory: rebuild the document in the requested format.
        try:
            converted = DocumentConverter(factory_for(format_name)).convert(nav.root)
        except ValueError as exc:
            print(exc)
            return
        print(converted.render() if converted.children else "(empty)")
        return

    show_ids = ctx.has("id")
    whole = ctx.has("whole")
    target = nav.root if whole else nav.cursor

    def render(element: TextElement) -> str:
        text = element.render()
        return f"[{nav.display_id(element)}] " + text if show_ids else text

    if isinstance(target, ContainerElement) and not isinstance(target, Root):
        print(render(target))
    else:
        if not target.children:
            print("(empty)")
            return
        for child in target.children:
            print(render(child))


def _cmd_add(nav: TextNavigator, ctx: Args) -> None:
    if len(ctx.positional) < 1:
        print("Usage: add <container|leaf> <type>")
        return
    category, *rest = ctx.positional
    element_type = rest[0] if rest else None

    if category == "container":
        title = input("Heading title: ").strip()
        level = input("Level [1]: ").strip() or "1"
        element = nav.create_and_attach(ElementKind.HEADING, title=title, level=level)
        print(f"Added heading '{title}' as [{nav.display_id(element)}].")
        return

    if category == "leaf":
        if element_type == "paragraph" or element_type is None:
            text = input("Paragraph text: ")
            element = nav.create_and_attach(ElementKind.PARAGRAPH, text=text)
        elif element_type == "link":
            label = input("Link label: ")
            url = input("URL: ")
            element = nav.create_and_attach(ElementKind.LINK, label=label, url=url)
        elif element_type == "image":
            alt_text = input("Alt text: ")
            source = input("Source: ")
            element = nav.create_and_attach(ElementKind.IMAGE, alt_text=alt_text, source=source)
        else:
            print(f"Unknown leaf type: {element_type}")
            return
        print(f"Added {element_type or 'paragraph'} as [{nav.display_id(element)}].")
        return

    print("Usage: add <container|leaf> <type>")


def _cmd_rm(nav: TextNavigator, ctx: Args) -> None:
    if nav.cursor.parent is None and not ctx.positional:
        print("Cannot remove the document root.")
        return

    if ctx.positional:
        name = ctx.positional[0]
        target = nav.find_child_by_name(name)
        if target is None:
            print(f"No such element here: {name}")
            return
        confirm = input(f"Remove '{nav.label(target)}'? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Cancelled.")
            return
        nav.cursor.remove_element(target)
        print(f"Removed '{nav.label(target)}'.")
        return

    confirm = input(f"Remove current element '{nav.label(nav.cursor)}'? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return
    parent = nav.cursor.parent
    parent.remove_element(nav.cursor)
    nav.cursor = parent
    print("Removed current element, moved to parent.")


def _cmd_up(nav: TextNavigator, ctx: Args) -> None:
    if not nav.go_up():
        print("Already at the root.")
    else:
        print(nav.pwd())


def _cmd_cd(nav: TextNavigator, ctx: Args) -> None:
    container_id = ctx.option("id")
    if container_id:
        if not nav.go_to_id(container_id):
            print(f"No such container id: {container_id}")
        else:
            print(nav.pwd())
        return

    if not ctx.positional:
        print("Usage: cd <path> | --id <container_id>")
        return

    path = ctx.positional[0]
    if not nav.go_to_path(path):
        print(f"No such path: {path}")
    else:
        print(nav.pwd())


def _cmd_save(nav: TextNavigator, repo: Repository, ctx: Args) -> None:
    if not ctx.positional:
        print("Usage: save <path.json>")
        return
    repo.save(ctx.positional[0], characters=[], items=[], abilities=[], document=nav.root)
    print(f"Saved document to {ctx.positional[0]}")


def _cmd_load(nav: TextNavigator, repo: Repository, ctx: Args) -> None:
    if not ctx.positional:
        print("Usage: load <path.json>")
        return
    try:
        state = repo.load(ctx.positional[0])
    except FileNotFoundError:
        print(f"No such file: {ctx.positional[0]}")
        return
    nav.replace_document(state["document"])
    print(f"Loaded document from {ctx.positional[0]}")


def _cmd_cp(nav: TextNavigator, ctx: Args) -> None:
    """Prototype: duplicates a child of the current element (with its
    whole subtree) right after the original."""
    if not ctx.positional:
        print("Usage: cp <elem_name>")
        return
    original = nav.find_child_by_name(ctx.positional[0])
    if original is None:
        print(f"No such element here: {ctx.positional[0]}")
        return
    copy = original.clone()
    nav.cursor.add(copy, nav.cursor.children.index(original) + 1)
    nav.register_subtree(copy)
    print(f"Copied '{nav.label(original)}' as [{nav.display_id(copy)}].")


def _cmd_template(nav: TextNavigator, templates: PrototypeRegistry, ctx: Args) -> None:
    """Prototype registry: save an element as a named template, list
    templates, or insert a fresh copy of one into the current element."""
    action = ctx.positional[0] if ctx.positional else ""
    if action == "ls":
        print(", ".join(templates.names()) or "(no templates)")
    elif action == "save" and len(ctx.positional) >= 3:
        element = nav.find_child_by_name(ctx.positional[2])
        if element is None:
            print(f"No such element here: {ctx.positional[2]}")
            return
        templates.register(ctx.positional[1], element)
        print(f"Saved '{nav.label(element)}' as template '{ctx.positional[1]}'.")
    elif action == "use" and len(ctx.positional) >= 2:
        try:
            element = templates.create(ctx.positional[1])
        except ValueError as exc:
            print(exc)
            return
        nav.attach(element)
        print(f"Inserted template '{ctx.positional[1]}' as [{nav.display_id(element)}].")
    else:
        print("Usage: template ls | template save <name> <elem_name> | template use <name>")


class TextDocumentStrategy(ICommandStrategy):
    """All commands of the structured-text mode. The existing command
    functions are adapted with FunctionCommand (Adapter)."""

    name = "text"
    title = "Structured text document"

    def __init__(self, nav: TextNavigator, repo: Repository | None = None,
                 templates: PrototypeRegistry | None = None) -> None:
        repo = repo or Repository()
        templates = templates or PrototypeRegistry()

        def cmd(name, fn, usage, description):
            return FunctionCommand(name, lambda args, cli: fn(args), usage, description)

        self._commands = [
            cmd("pwd", lambda a: _cmd_pwd(nav, a), "", "show current path in the document"),
            cmd("print", lambda a: _cmd_print(nav, a), "[--whole] [--id] [--format plain|markdown|html]",
                "print the current element or the whole document"),
            cmd("cp", lambda a: _cmd_cp(nav, a), "<elem_name>", "duplicate an element (Prototype)"),
            cmd("template", lambda a: _cmd_template(nav, templates, a), "ls | save <name> <elem> | use <name>",
                "element templates"),
            cmd("add", lambda a: _cmd_add(nav, a), "<container|leaf> <type>", "add an element (dialog)"),
            cmd("rm", lambda a: _cmd_rm(nav, a), "[elem_name]", "remove an element"),
            cmd("up", lambda a: _cmd_up(nav, a), "", "move to the parent element"),
            cmd("cd", lambda a: _cmd_cd(nav, a), "<path> | --id <container_id>", "move to an element"),
            cmd("save", lambda a: _cmd_save(nav, repo, a), "<path.json>", "persist the document"),
            cmd("load", lambda a: _cmd_load(nav, repo, a), "<path.json>", "restore a document"),
        ]

    def commands(self) -> list[Command]:
        return self._commands
