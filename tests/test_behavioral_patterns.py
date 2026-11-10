"""Tests for the behavioral patterns: Template Method, Memento, Command,
Observer (game side) and Iterator, Visitor (text side)."""

from dataclasses import replace

import pytest

from core.game import (
    Ability,
    ActionPerformed,
    ActionUndone,
    AttackCommand,
    Character,
    CharacterData,
    CombatStatistics,
    EquipCommand,
    Fireball,
    Game,
    GameCommand,
    GameObserver,
    HealCommand,
    HealingLight,
    Item,
    ItemData,
    StatusReported,
    UseAbilityCommand,
)
from core.text import (
    DepthFirstIterator,
    DocumentBuilder,
    Heading,
    HtmlElementFactory,
    Root,
    TextElementVisitor,
)
from data import Repository, text_serializer

from .doubles import MockDisplayer


def hero(name="Hero", health=100, armor=0, attack=10):
    return Character(CharacterData(name, health, health, armor, attack))


class RecordingObserver(GameObserver):
    def __init__(self):
        self.events = []

    def notify(self, event):
        self.events.append(event)


# -- Template Method ------------------------------------------------------------------


class Drain(Ability):
    """A brand-new ability written only through the two hooks."""

    name = "Drain"

    def _apply(self, user, recipient):
        dealt = recipient.take_damage(7, ignore_armor=True)
        user.heal(dealt)
        return dealt

    def to_data(self):
        raise NotImplementedError


def test_new_ability_only_implements_hooks():
    caster, target = hero(), hero()
    caster.take_damage(20)

    result = Drain().use(caster, target)

    assert result.message == "Hero uses Drain on Hero for 7 damage!"
    assert target.health == 93
    assert caster.health == 87


def test_template_checks_target_before_applying():
    with pytest.raises(ValueError, match="Drain requires a target"):
        Drain().use(hero(), None)


def test_self_cast_ability_targets_user():
    caster = hero()
    caster.take_damage(30)

    result = HealingLight(amount=10).use(caster)

    assert caster.health == 80
    assert result.message == "Hero casts Healing Light on Hero, healing 10 HP."


def test_subclasses_do_not_override_template():
    for cls in Ability.__subclasses__():
        assert "use" not in cls.__dict__, f"{cls.__name__} overrides the template method"


# -- Memento -------------------------------------------------------------------------


def test_memento_round_trip_restores_stats_equipment_and_abilities():
    character = hero(armor=2)
    snapshot = character.save_state()
    character.equip(Item(ItemData("Shield", {"armor": 5, "health": 10})))
    character.learn_ability(Fireball())
    character.take_damage(50, ignore_armor=True)
    character.defend()

    character.restore_state(snapshot)

    assert (character.health, character.max_health, character.armor) == (100, 100, 2)
    assert character.equipment == ()
    assert character.abilities == ()
    assert character.take_damage(10) == 8  # not defending anymore


def test_memento_exposes_no_state():
    snapshot = hero().save_state()

    assert [name for name in dir(snapshot) if not name.startswith("_")] == []
    with pytest.raises(AttributeError):
        snapshot.extra = 1


def test_memento_is_isolated_from_later_changes():
    character = hero()
    snapshot = character.save_state()
    character.take_damage(40)

    character.restore_state(snapshot)
    character.take_damage(10)
    character.restore_state(snapshot)

    assert character.health == 100


# -- Command ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "make_command",
    [
        lambda a, b: AttackCommand(a, b),
        lambda a, b: HealCommand(a, 20, b),
        lambda a, b: UseAbilityCommand(a, "Fireball", b),
        lambda a, b: EquipCommand(a, Item(ItemData("Sword", {"attack_power": 4}))),
    ],
)
def test_every_command_can_be_undone(make_command):
    a, b = hero("A"), hero("B")
    a.learn_ability(Fireball(damage=30))
    b.take_damage(30)
    before = (replace(a.data), replace(b.data), a.equipment)  # copies, not references

    command = make_command(a, b)
    command.execute()
    command.undo()

    assert (a.data, b.data, a.equipment) == before


def test_command_reports_health_changes():
    a, b = hero("A", attack=12), hero("B", armor=2)

    command = AttackCommand(a, b)
    command.execute()

    assert command.health_changes == {a: 0, b: -10}
    assert command.message == "A attacks B for 10 damage (target HP: 90/100)."


def test_command_cannot_run_twice_or_undo_before_running():
    command = AttackCommand(hero(), hero())
    with pytest.raises(RuntimeError):
        command.undo()
    command.execute()
    with pytest.raises(RuntimeError):
        command.execute()


def test_failing_command_leaves_no_partial_changes():
    class HalfwayFails(GameCommand):
        def __init__(self, character):
            super().__init__()
            self.character = character

        @property
        def actor(self):
            return self.character

        def affected(self):
            return [self.character]

        def _perform(self):
            self.character.take_damage(25)
            raise RuntimeError("boom")

    character = hero()
    with pytest.raises(RuntimeError):
        HalfwayFails(character).execute()

    assert character.health == 100


# -- Game as invoker + subject -----------------------------------------------------------


def test_undo_reverts_last_action_and_announces_it():
    displayer = MockDisplayer()
    game = Game(displayer)
    a, b = hero("A"), hero("B")
    game.basic_attack(a, b)
    game.basic_attack(a, b)

    undone = game.undo()

    assert isinstance(undone, AttackCommand)
    assert b.health == 90
    assert displayer.messages[-1] == "Undone: A attacks B for 10 damage (target HP: 80/100)."


def test_undo_is_last_in_first_out_and_stops_when_empty():
    game = Game(MockDisplayer())
    a, b = hero("A"), hero("B")
    game.basic_attack(a, b)
    game.heal(b, 5)

    game.undo()
    assert b.health == 90
    game.undo()
    assert b.health == 100
    assert game.undo() is None


def test_failed_action_is_not_recorded():
    game = Game(MockDisplayer())

    with pytest.raises(ValueError):
        game.use_ability(hero(), "Nope", hero())

    assert game.history == ()


def test_observers_receive_typed_events_in_order():
    game = Game(MockDisplayer())
    observer = RecordingObserver()
    game.subscribe(observer)
    a, b = hero("A"), hero("B")
    game.add_character(a)

    game.basic_attack(a, b)
    game.undo()
    game.report_status()

    assert [type(e) for e in observer.events] == [ActionPerformed, ActionUndone, StatusReported]
    assert observer.events[2].character is a


def test_unsubscribed_observer_gets_nothing_and_duplicates_are_ignored():
    game = Game(MockDisplayer())
    observer = RecordingObserver()
    game.subscribe(observer)
    game.subscribe(observer)

    game.basic_attack(hero(), hero())
    game.unsubscribe(observer)
    game.basic_attack(hero(), hero())

    assert len(observer.events) == 1


def test_statistics_tally_and_revert_on_undo():
    game = Game(MockDisplayer())
    stats = CombatStatistics()
    game.subscribe(stats)
    a, b = hero("A", attack=15), hero("B")
    b.learn_ability(HealingLight(amount=10))

    game.basic_attack(a, b)
    game.use_ability(b, "Healing Light")
    assert stats.damage_dealt["A"] == 15
    assert stats.damage_taken["B"] == 15
    assert stats.healing_done["B"] == 10

    game.undo()
    assert stats.healing_done["B"] == 0
    assert stats.report() == (
        "A: 1 actions, dealt 15, took 0, healed 0\n"
        "B: 0 actions, dealt 0, took 15, healed 0"
    )


def test_statistics_report_when_empty():
    assert CombatStatistics().report() == "No actions yet."


# -- Iterator ---------------------------------------------------------------------------


def nested_document(family=None) -> Root:
    return (
        DocumentBuilder(family)
        .heading("A").paragraph("a1")
            .heading("B").paragraph("b1").end()
            .paragraph("a2")
        .end()
        .heading("C").end()
        .build()
    )


def describe(element):
    return getattr(element, "title", None) or element.render()


def test_walk_is_pre_order_with_depths():
    walked = [(describe(e), d) for e, d in nested_document().walk()]

    assert walked == [("A", 1), ("a1", 2), ("B", 2), ("b1", 3), ("a2", 2), ("C", 1)]


def test_walk_can_include_the_start_node():
    doc = nested_document()

    first, depth = next(doc.walk(include_self=True))

    assert first is doc and depth == 0


def test_iterator_follows_the_protocol():
    iterator = Root().walk()

    assert isinstance(iterator, DepthFirstIterator)
    assert iter(iterator) is iterator
    with pytest.raises(StopIteration):
        next(iterator)


def test_walk_starting_inside_the_tree():
    section = nested_document().children[0].children[1]

    assert [describe(e) for e, _ in section.walk()] == ["b1"]


# -- Visitor -------------------------------------------------------------------------------


class CountingVisitor(TextElementVisitor[None]):
    def __init__(self):
        self.counts = {}

    def _count(self, kind):
        self.counts[kind] = self.counts.get(kind, 0) + 1

    def visit_root(self, root):
        self._count("root")
        for child in root.children:
            child.accept(self)

    def visit_heading(self, heading):
        self._count("heading")
        for child in heading.children:
            child.accept(self)

    def visit_paragraph(self, paragraph):
        self._count("paragraph")

    def visit_link(self, link):
        self._count("link")

    def visit_image(self, image):
        self._count("image")


def test_visitor_dispatches_by_element_kind():
    visitor = CountingVisitor()

    nested_document().accept(visitor)

    assert visitor.counts == {"root": 1, "heading": 3, "paragraph": 3}


def test_format_variants_dispatch_by_role():
    visitor = CountingVisitor()

    nested_document(HtmlElementFactory()).accept(visitor)

    assert visitor.counts == {"root": 1, "heading": 3, "paragraph": 3}


def test_visitor_must_handle_every_kind():
    class Incomplete(TextElementVisitor[None]):
        def visit_root(self, root):
            pass

    with pytest.raises(TypeError):
        Incomplete()


def test_serializing_visitor_output():
    doc = DocumentBuilder().heading("T").link("L", "u").end().image("I", "s").build()

    assert text_serializer.document_to_dict(doc) == {
        "type": "root",
        "children": [
            {"type": "heading", "title": "T", "level": 1,
             "children": [{"type": "link", "label": "L", "url": "u"}]},
            {"type": "image", "alt_text": "I", "source": "s"},
        ],
    }


def test_visitor_based_round_trip_keeps_heading_types():
    restored = text_serializer.dict_to_document(text_serializer.document_to_dict(nested_document()))

    assert isinstance(restored.children[0].children[1], Heading)
    assert restored.render() == nested_document().render()


# -- CLI ---------------------------------------------------------------------------------------


def test_undo_and_stats_commands(chars):
    chars.run("create char", "A", "100", "0", "12", "", "", "")
    chars.run("create char", "B", "100", "0", "5", "", "", "")

    chars.run("act attack c1 c2")
    chars.run("act attack c1 c2")
    undo_out = chars.run("undo")
    out = chars.run("stats")

    assert chars.catalog.find_character("B").health == 88
    assert undo_out.startswith("Undone: A attacks B")
    rows = [line.split("│") for line in out.splitlines()[3:]]
    assert [[cell.strip() for cell in row] for row in rows] == [
        ["A", "1", "12", "0", "0"],
        ["B", "0", "0", "12", "0"],
    ]
    # the text report used by other code is unchanged
    assert chars.ctx.stats.report().splitlines()[0] == "A: 1 actions, dealt 12, took 0, healed 0"


def test_undo_with_empty_history(chars):
    assert "Nothing to undo." in chars.run("undo")
