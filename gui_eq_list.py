import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib
import numpy as np
import os

from fin_equiv import FinEquiv

class RenameableLabel(Gtk.EventBox):
    def __init__(self, name):
        super().__init__()
        self.label = Gtk.Label(label = name)
        self.set_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                        Gdk.EventMask.POINTER_MOTION_MASK
                        )
        self.connect("button-press-event", self.on_button_press)
        self.entry = None
        self.add(self.label)

    def on_button_press(self,w,e):
        if e.type != Gdk.EventType.BUTTON_PRESS: return False
        if e.button != 3: return False
        if self.entry is not None: return False

        self.remove(self.label)
        self.entry = Gtk.Entry()
        self.entry.show_all()
        self.entry.set_text(self.label.get_text())
        self.add(self.entry)
        self.entry.grab_focus()
        self.entry.connect("focus-out-event", self.confirm_edit)
        self.entry.connect("activate", self.confirm_edit)

    def confirm_edit(self, *args):
        if self.entry is None: return
        entry = self.entry
        self.label.set_text(self.entry.get_text())
        self.entry = None
        self.remove(entry)
        self.add(self.label)

class EquivListRow(Gtk.ListBoxRow):
    def __init__(self, name, equiv, is_generator, edit_mode):
        super().__init__()
        self.equiv = equiv
        self.is_generator = is_generator
        self.last_edit_mode = edit_mode

        handle = Gtk.EventBox() # to be capable of receiving DnD
        self.add(handle)

        self.drag_dest_set(
            Gtk.DestDefaults.ALL,
            [],
            Gdk.DragAction.MOVE
        )
        self.connect("drag-data-received", self.on_drop)
        self.drag_dest_add_text_targets()
        self.connect("state-flags-changed", self.on_state_flags_changed)

        handle.drag_source_set(
            Gdk.ModifierType.BUTTON1_MASK,
            [],
            Gdk.DragAction.MOVE
        )
        handle.connect("drag-data-get", self.get_drag_data)
        handle.drag_source_add_text_targets()

        hbox = Gtk.HBox()
        handle.add(hbox)

        self.del_button = Gtk.Button.new_from_icon_name("window-close", Gtk.IconSize.SMALL_TOOLBAR)
        self.del_box = Gtk.Box()
        if edit_mode or not is_generator:
            self.del_box.add(self.del_button)
        else:
            self.del_button.show_all()
        hbox.pack_start(self.del_box, False, False, 0)
        self.label = RenameableLabel(name)
        hbox.add(self.label)
        add_button = Gtk.Button.new_from_icon_name("list-add", Gtk.IconSize.SMALL_TOOLBAR)
        sub_button = Gtk.Button.new_from_icon_name("list-remove", Gtk.IconSize.SMALL_TOOLBAR)
        hbox.pack_end(sub_button, False, False, 0)
        hbox.pack_end(add_button, False, False, 0)
        for button in (self.del_button, sub_button, add_button):
            button.set_relief(Gtk.ReliefStyle.NONE)
        self.del_button.connect("clicked", self.delete)
        add_button.connect("clicked", self.join_with_current)
        sub_button.connect("clicked", self.meet_with_current)

        self.show_all()

    @property
    def name(self):
        return self.label.label.get_text()

    def on_state_flags_changed(self, w, flags):
        prelight = bool(w.get_state_flags() & (Gtk.StateFlags.PRELIGHT | Gtk.StateFlags.DROP_ACTIVE))
        listbox = self.get_parent()
        if prelight: listbox.set_preview(self.equiv)
        elif listbox.preview == self.equiv: listbox.set_preview(None)

    def set_edit_mode(self, edit_mode):
        if self.last_edit_mode == edit_mode: return
        self.last_edit_mode = edit_mode
        if not self.is_generator: self.delete()
        elif edit_mode: self.del_box.add(self.del_button)
        else: self.del_box.remove(self.del_button)


    def export_state(self):
        return {
            "name" : self.name,
            "is_generator" : self.is_generator,
            "equiv" : self.equiv.classes,
        }
    @staticmethod
    def from_state(state, num_nodes, edit_mode):
        return EquivListRow(
            name = state['name'],
            equiv = FinEquiv(num_nodes, state['equiv']),
            is_generator = state['is_generator'],
            edit_mode = edit_mode,
        )

    # button events

    def delete(self, *args):
        if self.is_generator and not self.last_edit_mode:
            print("How did it happen? Deletion should not be available for generators in Generate mode")
            return
        listbox = self.get_parent()
        listbox.data_s.remove(self.equiv)
        listbox.remove(self)
    def join_with_current(self, *args):
        listbox = self.get_parent()
        gui = listbox.gui
        gui.set_equiv(gui.equivalence | self.equiv)
    def meet_with_current(self, *args):
        listbox = self.get_parent()
        gui = listbox.gui
        gui.set_equiv(gui.equivalence & self.equiv)

    # Drag & Drop

    def get_drag_data(self, handle, context, data, info, time):
        src_index = self.get_index()
        data.set_text(str(src_index), -1)
    def on_drop(self, row, drag_context, x, y, data, info, time):
        src_index = data.get_text()
        if not src_index.isnumeric(): return
        src_index = int(src_index)

        listbox = row.get_parent()
        children = listbox.get_children()
        if not 0 <= src_index < len(children)-1: return

        dest_index = row.get_index()
        moved = children[src_index]
        listbox.remove(moved)
        listbox.insert(moved, dest_index)

class EquivList(Gtk.ListBox):
    def __init__(self, gui):
        super().__init__()
        self.data_s = set()
        self.last_i = 0
        self.preview = None
        self.gui = gui
        self.set_selection_mode(Gtk.SelectionMode.NONE)
        new_button = Gtk.Button.new_from_icon_name("list-add", Gtk.IconSize.SMALL_TOOLBAR)
        new_button.set_tooltip_text("Add current (F2)")
        new_button.connect("clicked", self.add_current)
        self.add(new_button)

        self.set_property('can-focus', True)
        self.connect("button-press-event", self.on_button_press)
        self._edit_mode = True

    @property
    def edit_mode(self):
        return self._edit_mode
    @edit_mode.setter
    def edit_mode(self, x):
        x = bool(x)
        if self._edit_mode == x: return
        self._edit_mode = x
        for row in self.get_rows():
            row.set_edit_mode(x)

    def get_data(self):
        for row in self.get_rows():
            yield row.equiv
    def get_generators(self):
        for row in self.get_rows():
            if row.is_generator:
                yield row.equiv

    def add_current(self, *args):
        equiv = self.gui.equivalence
        if equiv in self.data_s:
            row = next(row for row in self.get_children() if row.equiv == equiv)
            self.remove(row)
            self._add_row(row)
        else:
            self.last_i += 1
            used_names = set(row.name for row in self.get_rows())
            if self._edit_mode: prefix = "Generator "
            else: prefix = "Equivalence "
            i = 1
            while prefix+str(i) in used_names: i += 1
            name = prefix+str(i)

            self.data_s.add(equiv)
            self._add_row(EquivListRow(name, equiv, self._edit_mode, self._edit_mode))

    def get_rows(self):
        return [row for row in self.get_children() if isinstance(row, EquivListRow)]
    def _add_row(self, row):
        self.insert(row, len(self.get_children())-1)

    def on_button_press(self, w,e):
        if e.type != Gdk.EventType.BUTTON_PRESS: return False
        if e.button == 1: self.grab_focus()

    def set_preview(self, equiv):
        self.preview = equiv
        self.gui.darea.queue_draw()

    def export_state(self):
        return {
            "edit_mode" : self._edit_mode,
            "rows" : [row.export_state() for row in self.get_rows()],
        }
    def import_state(self, state):
        self._edit_mode = state['edit_mode']
        for row in self.get_rows():
            self.remove(row)
        for row in state['rows']:
            self._add_row(EquivListRow.from_state(row, self.gui.num_nodes, self._edit_mode))
        self.data_s = set(self.get_data())
