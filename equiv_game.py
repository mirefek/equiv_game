#!/usr/bin/python3

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib
import numpy as np
import os
import random
import argparse
import json

from gui_tool import EditTool, GenerateTool
from fin_equiv import FinEquiv, bell_number
from gui_eq_list import EquivList

class EquivalencesGUI(Gtk.Window):
    def __init__(self, num_nodes, load_on_start, save_on_quit, win_size = (1100,800)):
        super().__init__()

        self.nodes = [
            (np.sin(x), np.cos(x))
            for x in np.linspace(0, 2*np.pi, num_nodes+1)[:-1]
        ]
        self.num_nodes = num_nodes
        self.equivalence = FinEquiv.random(num_nodes)

        self.node_radius = 10
        self.node_neighborhood = 2*self.node_radius
        self.max_challenges = 4
        self.last_verified = None

        self.basic_tool = EditTool(self)
        self.tool = self.basic_tool
        self.darea = Gtk.DrawingArea()
        self.equiv_list = EquivList(self)
        self.cur_challenge = None
        self.min_gen = bell_number(self.num_nodes)+1
        self._num_solved = 0

        vbox = Gtk.VBox()
        self.add(vbox)

        toolbar = Gtk.HBox()

        self.edit_button = Gtk.RadioButton.new_with_label_from_widget(None, "Edit")
        self.edit_button.set_tooltip_text("Equivalence Edit Mode (F4)")
        self.edit_button.set_mode(False)
        self.edit_button.connect("toggled", self.edit_mode_clicked)
        toolbar.pack_start(self.edit_button, False, False, 0)
        self.generate_button = Gtk.RadioButton.new_with_label_from_widget(self.edit_button, "Generate")
        self.generate_button.set_tooltip_text("Lattice Generation Mode (F5)")
        self.generate_button.set_mode(False)
        self.generate_button.connect("toggled", self.generate_mode_clicked)
        toolbar.pack_start(self.generate_button, False, False, 0)
        self.challenge_button = Gtk.RadioButton.new_with_label_from_widget(self.edit_button, "Challenge")
        self.challenge_button.set_tooltip_text("Show that your generators work (F6)")
        self.challenge_button.set_mode(False)
        self.challenge_button.connect("toggled", self.challenge_mode_clicked)
        subvbox = Gtk.VBox()
        subvbox.add(self.challenge_button)

        self.solved_progress_bar = Gtk.ProgressBar()
        subvbox.pack_end(self.solved_progress_bar, False, False, 0)
        toolbar.pack_start(subvbox, False, False, 0)

        self.label_best_sol = Gtk.Label(label = "no solution yet...")
        toolbar.pack_start(self.label_best_sol, False, False, 20)

        undo_button = Gtk.Button.new_from_icon_name("edit-undo", Gtk.IconSize.LARGE_TOOLBAR)
        empty_button = Gtk.Button.new_from_icon_name("input-dialpad-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
        full_button = Gtk.Button.new_from_icon_name("weather-overcast-symbolic", Gtk.IconSize.LARGE_TOOLBAR)

        undo_button.set_tooltip_text("Undo (Backspace)")
        full_button.set_tooltip_text("Full Equivalence (2)")
        empty_button.set_tooltip_text("Empty Equivalence (1)")
        toolbar.pack_end(undo_button, False, False, 0)
        toolbar.pack_end(full_button, False, False, 0)
        toolbar.pack_end(empty_button, False, False, 0)
        undo_button.connect("clicked", self.undo)
        full_button.connect("clicked", self.set_full)
        empty_button.connect("clicked", self.set_empty)
        
        vbox.pack_start(toolbar, False, False, 0)

        hpaned = Gtk.HPaned()
        vbox.add(hpaned)
        scrolled = Gtk.ScrolledWindow()
        scrolled.add(self.equiv_list)
        hpaned.pack1(scrolled, False, True)
        hpaned.pack2(self.darea, True, False)
        hpaned.set_position(300)

        self.darea.connect("draw", self.on_draw)
        self.set_events(Gdk.EventMask.KEY_PRESS_MASK)
        self.darea.set_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                              Gdk.EventMask.BUTTON_RELEASE_MASK |
                              Gdk.EventMask.SCROLL_MASK |
                              Gdk.EventMask.POINTER_MOTION_MASK
                              )

        self.connect("destroy", self.quit_app)
        self.connect("key-press-event", self.on_key_press)
        self.darea.connect("button-press-event", self.on_button_press)
        self.darea.connect("button-release-event", self.on_button_release)
        self.darea.connect("scroll-event", self.on_scroll)
        self.darea.connect("motion-notify-event", self.on_motion)
        self.darea.set_property('can-focus', True)

        self.set_title("Equivalence Problem")
        self.resize(*win_size)
        self.hsv = Gtk.HSV()

        self.scale = 100
        self.shift = (0,0)
        self.show_all()
        if load_on_start: self.load_state()
        self.save_on_quit = save_on_quit

    @property
    def num_solved(self):
        return self._num_solved
    @num_solved.setter
    def num_solved(self, x):
        self._num_solved = x
        if x == 0: self.solved_progress_bar.set_fraction(0)
        else: self.solved_progress_bar.set_fraction(x / len(self.challenges))

    def update_win_size(self):
        self.win_size = (self.darea.get_allocated_width(), self.darea.get_allocated_height())

    def pixel_to_coor(self, pixel):
        px,py = pixel
        w,h = self.win_size
        sx,sy = self.shift
        x = (px - w/2) / self.scale - sx
        y = (h/2 - py) / self.scale - sy
        return (x,y)
    def coor_to_pixel(self, pos):
        w,h = self.win_size
        sx,sy = self.shift
        x,y = pos
        x = float(x)
        y = float(y)
        px = (x + sx) * self.scale + w/2
        py = h/2 - (y + sy) * self.scale
        return px,py
    def set_shift(self, pixel, coor):
        w,h = self.win_size
        px,py = pixel
        x,y = coor
        sx = (px - w/2) / self.scale - x
        sy = (h/2 - py) / self.scale - y
        self.shift = sx,sy

    def on_scroll(self,w,e):
        coor = self.pixel_to_coor((e.x, e.y))
        if e.direction == Gdk.ScrollDirection.DOWN: self.scale *= 0.9
        elif e.direction == Gdk.ScrollDirection.UP: self.scale /= 0.9
        # print("zoom {}".format(self.scale))
        self.set_shift((e.x, e.y), coor)
        self.darea.queue_draw()

    def find_node(self, pixel, tolerance = 1):
        px,py = pixel
        pixel_nodes = [self.coor_to_pixel(node) for node in self.nodes]
        sq_dist, node = min(
            ((x-px)**2 + (y-py)**2, i)
            for i,(x,y) in enumerate(pixel_nodes)
        )
        if (sq_dist / tolerance**2) < self.node_neighborhood**2: return node
        else: return None

    def set_equiv(self, equiv):
        self.save_undo()
        self.equivalence = equiv
        self.check_challenge()
        self.darea.queue_draw()
    def set_empty(self, *args):
        self.tool = self.basic_tool
        self.set_equiv(self.tool.empty_equiv)
    def set_full(self, *args):
        self.tool = self.basic_tool
        self.set_equiv(self.tool.full_equiv)

    def on_key_press(self,w,e):
        keyval = e.keyval
        keyval_name = Gdk.keyval_name(keyval)
        # print(keyval_name)
        if keyval_name == 'Escape': self.quit_app()
        if keyval_name == '1': self.set_empty()
        if keyval_name == '2': self.set_full()
        if keyval_name == 'BackSpace': self.undo()
        if keyval_name == 'F2': self.equiv_list.add_current()
        if keyval_name == 'F4': self.edit_button.set_active(True)
        if keyval_name == 'F5': self.generate_button.set_active(True)
        if keyval_name == 'F6': self.challenge_button.set_active(True)

    def quit_app(self, *args):
        if self.save_on_quit: self.save_state()
        Gtk.main_quit()

    def edit_mode_clicked(self, button):
        if not button.get_active(): return
        self.end_generate_mode()
        self.darea.queue_draw()
    def generate_mode_clicked(self, button):
        if not button.get_active(): return
        self.cur_challenge = None
        self.start_generate_mode()
        self.darea.queue_draw()
    def challenge_mode_clicked(self, button):
        if not button.get_active(): return
        if self.cur_challenge is not None: return
        if self.start_generate_mode():
            self.start_challenge()
        self.darea.queue_draw()

    def start_generate_mode(self):
        if not self.equiv_list.edit_mode: return True
        try:
            basic_tool = GenerateTool(self)
        except Exception as e:
            self.edit_button.set_active(True)

            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.CANCEL,
                text="Failed",
            )
            dialog.format_secondary_text(str(e))
            dialog.run()
            dialog.destroy()

            return False
        self.basic_tool = basic_tool
        self.tool = basic_tool
        self.challenges = self.generate_challenges()
        if self.challenges: self.was_solved = False
        else: self.was_solved = True
        self.cur_challenge = None
        self.num_solved = 0
        self.equiv_list.edit_mode = False
        return True
    def start_challenge(self):
        if self.num_solved >= len(self.challenges):
            self.generate_button.set_active(True)
            if self.was_solved:
                dialog = Gtk.MessageDialog(
                    transient_for=self,
                    flags=0,
                    message_type=Gtk.MessageType.INFO,
                    buttons=Gtk.ButtonsType.OK,
                    text="Done!"
                )
                dialog.format_secondary_text("The challenges were already solved.")
                dialog.run()
                dialog.destroy()
            else:
                dialog = Gtk.MessageDialog(
                    transient_for=self,
                    flags=0,
                    message_type=Gtk.MessageType.INFO,
                    buttons=Gtk.ButtonsType.OK,
                    text="Congratulations!"
                )
                generators = list(self.equiv_list.get_generators())
                num_gen = len(generators)
                dialog.format_secondary_text(f"You solved the challenges using {num_gen} generators. Could there be a better solution?")
                dialog.run()
                dialog.destroy()
                self.last_verified = generators
                self.min_gen = min(num_gen, self.min_gen)
                self.label_best_sol.set_text(f"Record: {self.min_gen} generators")

            self.was_solved = True
            return False
        self.cur_challenge = self.challenges[self.num_solved]
        self.check_challenge()
        return True
    def check_challenge(self):
        if self.cur_challenge is None: return
        if self.cur_challenge == self.equivalence:
            self.num_solved += 1
            self.cur_challenge = None
            self.start_challenge()

    def end_generate_mode(self):
        self.cur_challenge = None
        if self.equiv_list.edit_mode: return
        del self.challenges
        self.num_solved = 0
        self.basic_tool = EditTool(self)
        self.tool = self.basic_tool
        self.equiv_list.edit_mode = True

    def on_button_press(self, w, e):
        self.darea.grab_focus()
        if e.type != Gdk.EventType.BUTTON_PRESS: return
        if e.button == 1: self.tool.on_left_click((e.x, e.y))
        elif e.button == 2: self.tool.on_middle_click((e.x, e.y))
        elif e.button == 3: self.tool.on_right_click((e.x, e.y))
    def on_motion(self, w, e):
        self.tool.on_motion((e.x, e.y))
    def on_button_release(self, w, e):
        self.tool.on_release((e.x, e.y))

    def draw_node(self, cr, node_i):
        x,y = self.coor_to_pixel(self.nodes[node_i])
        cr.set_source_rgb(0,0,0)
        cr.arc(x, y, self.node_radius, 0, 2*np.pi)
        cr.fill()
    def draw_isolated(self, cr, p):
        x,y = self.coor_to_pixel(self.nodes[p])
        cr.set_source_rgba(0.5,0.5,0.5,0.5)
        cr.arc(x, y, self.node_neighborhood, 0, 2*np.pi)
        cr.fill()
    def draw_comp(self, cr, c, i):
        hue = (i / len(self.display_equiv.nontriv_classes) + 0.5) % 1
        color = self.hsv.to_rgb(hue, 1, 1)
        nodes = [
            self.nodes[p]
            for p in c
        ]

        # reorder nodes to minimize zig-zags
        best_pair = (None, None, None)
        for i,(x1,y1) in enumerate(nodes):
            for j,(x2,y2) in enumerate(nodes):
                if j >= i: continue
                sq_dist = (x1-x2)**2 + (y1-y2)**2
                if best_pair[2] is None or sq_dist < best_pair[2]:
                    best_pair = i,j,sq_dist
        remains = set(range(len(nodes)))
        i,j,_ = best_pair
        remains.remove(i)
        remains.remove(j)
        start = [i]
        end = [j]
        while remains:
            x,y = nodes[start[-1]]
            dist_start,i = min(((nodes[i][0]-x)**2 + (nodes[i][1]-y)**2,i) for i in remains)
            x,y = nodes[end[-1]]
            dist_end,j = min(((nodes[j][0]-x)**2 + (nodes[j][1]-y)**2,j) for j in remains)
            if dist_start < dist_end:
                start.append(i)
                remains.remove(i)
            else:
                end.append(j)
                remains.remove(j)

        nodes = [
            self.coor_to_pixel(nodes[i])
            for i in list(reversed(start)) + end
        ]
        
        cr.set_source_rgba(*color,0.5)
        cr.move_to(*nodes[0])
        for coor in nodes[1:]:
            cr.line_to(*coor)
        cr.set_line_width(2*self.node_neighborhood)
        cr.set_line_cap(1)
        cr.set_line_join(1)
        cr.stroke()

    def highlight_node(self, cr, node, with_comp):
        radius = 0.6 * self.node_radius
        if with_comp:
            ci = self.display_equiv.node_to_class[node]
            c = self.display_equiv.classes[ci]
        else:
            c = [node]
        for n in c:
            x,y = self.coor_to_pixel(self.nodes[n])
            if n == node: cr.set_source_rgb(1.0,1.0,0.0)
            else: cr.set_source_rgb(0.8,0.8,0.8)
            cr.arc(x, y, radius, 0, 2*np.pi)
            cr.fill()

    def fill_background(self,cr):
        cr.rectangle(0,0,*self.win_size)
        cr.set_source_rgb(1, 1, 1)
        cr.fill()

    def on_draw(self, wid, cr):
        self.update_win_size()
        self.fill_background(cr)

        self.display_equiv = self.equivalence
        self.draw_graph(cr)
        self.draw_preview(cr)

    def draw_graph(self, cr):
        for i,c in enumerate(self.display_equiv.nontriv_classes):
            self.draw_comp(cr, c,i)
        for x in self.display_equiv.isolated_nodes:
            self.draw_isolated(cr, x)

        for i in range(len(self.nodes)):
            self.draw_node(cr, i)

        self.tool.display_fg(cr)

    def draw_preview(self, cr):
        goal_border = False
        equiv = self.tool.previewed_equiv()
        if equiv is None: equiv = self.equiv_list.preview
        if equiv is None:
            equiv = self.cur_challenge
            goal_border = True
        if equiv is None: return
        self.display_equiv = equiv

        xs, ys = zip(*(self.coor_to_pixel(coor) for coor in self.nodes))
        inner_border = 50
        outer_border = 10
        min_x = min(xs) - self.node_neighborhood - inner_border
        min_y = min(ys) - self.node_neighborhood - inner_border
        max_x = max(xs) + self.node_neighborhood + inner_border
        max_y = max(ys) + self.node_neighborhood + inner_border
        ww,wh = self.win_size
        sw,sh = max_x-min_x, max_y-min_y
        scale = 0.3*min(wh/sh, ww/sw)

        cr.save()
        cr.translate(outer_border, outer_border)
        cr.scale(scale, scale)

        cr.rectangle(0,0,sw,sh)
        cr.set_source_rgba(0.0, 0.0, 0.0, 0.05)
        if goal_border:
            cr.fill_preserve()
            cr.set_source_rgb(0.0, 0.5, 0.0)
            cr.set_line_width(3/scale)
            cr.stroke()
        else:
            cr.fill()

        cr.translate(-min_x, -min_y)
        self.draw_graph(cr)
        cr.restore()

    def save_undo(self):
        if self.undo_stack and self.undo_stack[-1] == self.equivalence: return
        self.undo_stack.append(self.equivalence)
    def undo(self, *args):
        while self.undo_stack:
            eq = self.undo_stack.pop()
            if eq != self.equivalence:
                self.equivalence = eq
                self.darea.queue_draw()
                break
        self.check_challenge()

    def generate_challenges(self):
        used = set(self.equiv_list.data_s)
        used.add(self.basic_tool.empty_equiv)
        used.add(self.basic_tool.full_equiv)
        if self.last_verified is None and 2*(len(used)+self.max_challenges) < bell_number(self.num_nodes):
            challenges = []
            for _ in range(self.max_challenges):
                equiv = FinEquiv.random(self.num_nodes)
                if equiv in used: continue
                used.add(equiv)
                challenges.append(equiv)
            return challenges
        else:
            if self.last_verified is None:
                all_to_check = set(FinEquiv.collect_all(self.num_nodes))
            else:
                all_to_check = set(self.last_verified)
            remaining = list(all_to_check - used)
            random.shuffle(remaining)
            return remaining[:self.max_challenges]

    def export_state(self):
        state = {
            "zoom" : self.scale,
            "shift" : self.shift,
            "nodes" : self.nodes,
            "equivalence" : self.equivalence.classes,
            "equiv_list" : self.equiv_list.export_state(),
            "num_solved" : self.num_solved,
        }
        if self.cur_challenge is not None:
            state["cur_challenge"] = self.cur_challenge.classes
        if self.last_verified is not None:
            state["last_verified"] = [
                equiv.classes for equiv in self.last_verified
            ]
            state["min_gen"] = self.min_gen
        if not self.equiv_list.edit_mode:
            state["challenges"] = [x.classes for x in self.challenges]
        return state

    def import_state(self, state):
        self.scale = state['zoom']
        self.shift = tuple(state['shift'])
        self.nodes = [(x,y) for (x,y) in state['nodes']]
        self.num_nodes = len(self.nodes)
        n = self.num_nodes
        self.equivalence = FinEquiv(n, state['equivalence'])
        self.equiv_list.import_state(state['equiv_list'])
        if "cur_challenge" in state:
            self.cur_challenge = FinEquiv(n, state["cur_challenge"])
        else:
            self.cur_challenge = None
            
        if 'last_verified' in state:
            self.last_verified = [
                FinEquiv(n, classes)
                for classes in state['last_verified']
            ]
            self.min_gen = state["min_gen"]
            self.label_best_sol.set_text(f"Record: {self.min_gen} generators")
        else:
            self.label_best_sol.set_text("no solution yet...")
        if not self.equiv_list.edit_mode:
            self.challenges = [FinEquiv(n, classes) for classes in state["challenges"]]

        self.num_solved = state["num_solved"] # set last because of the progress bar

        if self.equiv_list.edit_mode:
            self.edit_button.set_active(True)
            self.basic_tool = EditTool(self)
        else:
            equiv = self.equivalence
            self.basic_tool = GenerateTool(self)
            self.equivalence = equiv
            if self.cur_challenge is None:
                self.generate_button.set_active(True)
            else:
                self.challenge_button.set_active(True)
            self.was_solved = self.num_solved == len(self.challenges)
        self.tool = self.basic_tool

        self.darea.queue_draw()

    def _get_fname(self):
        dir_path = os.path.dirname(os.path.realpath(__file__))
        fname = os.path.join(dir_path, f"saved_{self.num_nodes}.json")
        return fname
        
    def save_state(self, fname = None):
        if fname is None: fname = self._get_fname()
        state = self.export_state()
        with open(fname, 'w') as f: json.dump(state, f)
    def load_state(self, fname = None):
        if fname is None: fname = self._get_fname()
        if not os.path.isfile(fname): return
        with open(fname) as f: state = json.load(f)
        self.import_state(state)
        self.darea.queue_draw()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('num_nodes', type=int, nargs='?', default=10)
    parser.add_argument("--reset", action = "store_true", help="don't load state at the start")
    parser.add_argument("--try", action = "store_true", help="don't save state at the end")

    args = parser.parse_args()
    assert args.num_nodes > 0
    win = EquivalencesGUI(
        num_nodes = args.num_nodes,
        load_on_start = not args.reset,
        save_on_quit = not getattr(args, 'try'),
    )
    Gtk.main()
