import random
from fin_equiv import FinEquiv

class Tool:
    def __init__(self, gui):
        self.gui = gui
    def on_motion(self, pixel):
        pass
    def on_left_click(self, pixel):
        self.reset_tool()
    def on_middle_click(self, pixel):
        self.reset_tool()
    def on_right_click(self, pixel):
        self.reset_tool()
    def on_release(self, pixel):
        self.reset_tool()
    def display_fg(self, cr):
        pass
    def previewed_equiv(self):
        return None

    def set_tool(self, tool, *args, **kwargs):
        self.gui.tool = tool(self.gui, *args, **kwargs)
    def reset_tool(self):
        self.gui.tool = self.gui.basic_tool
        self.redraw()
    def redraw(self):
        self.gui.darea.queue_draw()

class BasicTool(Tool):
    def __init__(self, gui):
        super().__init__(gui)
        self.hl_node = None
        self.gui.undo_stack = []
    def on_left_click(self, pixel):
        node = self.gui.find_node(pixel, tolerance = 2)
        self.hl_node = None
        self.gui.save_undo()
        self.set_tool(self.join_tool, node)
        self.redraw()
    def on_right_click(self, pixel):
        node = self.gui.find_node(pixel, tolerance = 2)
        self.hl_node = None
        self.gui.save_undo()
        self.set_tool(self.meet_tool, node)
        self.redraw()
    def on_middle_click(self, pixel):
        node = self.gui.find_node(pixel, tolerance = 2)
        if node is None:
            self.hl_node = None
            self.set_tool(
                MoveView,
                grasp = self.gui.pixel_to_coor(pixel),
            )
        else:
            self.hl_node = None
            self.set_tool(MoveNode, node)
    def on_motion(self, pixel):
        node = self.gui.find_node(pixel, tolerance = 2)
        if node != self.hl_node:
            self.hl_node = node
            self.redraw()
    def display_fg(self, cr):
        if self.hl_node is not None:
            self.gui.highlight_node(cr, self.hl_node, True)
    
class EditTool(BasicTool):
    def __init__(self, gui):
        super().__init__(gui)
        self.empty_equiv = FinEquiv.empty(gui.num_nodes)
        self.full_equiv = FinEquiv.full(gui.num_nodes)
        self.join_tool = JoinNodes
        self.meet_tool = SeparateNodes

class MoveView(Tool):
    def __init__(self, gui, grasp):
        super().__init__(gui)
        self.grasp = grasp
    def on_motion(self, pixel):
        self.gui.set_shift(pixel, self.grasp)
        self.redraw()

class NodeTool(Tool):
    def __init__(self, gui, node):
        super().__init__(gui)
        self.node = node
    def display_fg(self, cr):
        if self.node is not None:
            self.gui.highlight_node(cr, self.node, True)
    
class MoveNode(NodeTool):
    def on_motion(self, pixel):
        coor = self.gui.pixel_to_coor(pixel)
        self.gui.nodes[self.node] = coor
        self.redraw()

class JoinNodes(NodeTool):
    def join_classes(self, node):
        equiv = self.gui.equivalence
        ci1 = equiv.node_to_class[node]
        ci2 = equiv.node_to_class[self.node]
        if ci1 == ci2: return
        classes = [
            equiv.classes[ci1] + equiv.classes[ci2]
        ] + [
            c for i,c in enumerate(equiv.classes)
            if i != ci1 and i != ci2
        ]
        self.node = node
        self.gui.equivalence = FinEquiv(equiv.num_nodes, classes)

    def on_motion(self, pixel):
        node = self.gui.find_node(pixel)
        if node is None or node == self.node: return
        if self.node is None:
            self.node = node
        else:
            self.join_classes(node)
        self.redraw()

class SeparateNodes(Tool):
    def __init__(self, gui, node):
        super().__init__(gui)
        if node is not None:
            self.separate_node(node)
    def separate_node(self, node):
        equiv = self.gui.equivalence
        ci = equiv.node_to_class[node]
        cl = equiv.classes[ci]
        if len(cl) == 1: return False
        cl = list(cl)
        cl.remove(node)
        classes = [
            c for i,c in enumerate(equiv.classes)
            if i != ci
        ] + [
            cl, (node,)
        ]
        self.gui.equivalence = FinEquiv(equiv.num_nodes, classes)
        self.redraw()
    def on_motion(self, pixel):
        node = self.gui.find_node(pixel)
        if node is not None:
            self.separate_node(node)

class GenerateTool(BasicTool):
    def __init__(self, gui):
        super().__init__(gui)
        self.empty_equiv = None
        self.full_equiv = None
        for eq in gui.equiv_list.get_generators():
            if self.empty_equiv is None:
                self.empty_equiv = eq
                self.full_equiv = eq
            else:
                self.empty_equiv = self.empty_equiv & eq
                self.full_equiv = self.full_equiv | eq
        if self.empty_equiv is None:
            raise Exception("To use generate mode, we need a nonempty set of generators")
        self.gui.equivalence = eq
        self.join_tool = JoinEquiv
        self.meet_tool = MeetEquiv
        self.redraw()

class LatticeStep(Tool):
    def __init__(self, gui, node):
        super().__init__(gui)
        if node is None: self.nodes = set()
        else: self.nodes = set([node])
        self.find_candidate()

    def on_motion(self, pixel):
        node = self.gui.find_node(pixel)
        if node is None: return
        if node in self.nodes: return
        self.nodes.add(node)
        self.find_candidate()
        self.redraw()
    def on_release(self, pixel):
        if self.candidate is not None:
            self.gui.set_equiv(self.use_equiv(self.candidate))
        self.reset_tool()

    def equiv_fits(self, equiv):
        cis = [equiv.node_to_class[n] for n in self.nodes]
        assert len(cis) > 0
        if len(cis) == 1:
            [ci] = cis
            return len(equiv.classes[ci]) == 1
        else:
            return all(ci == cis[0] for ci in cis)
        
    def find_candidate(self):
        if not self.nodes:
            self.candidate = None
        else:
            candidates = [
                cand
                for cand in self.gui.equiv_list.get_data()
                if self.equiv_fits(cand)
            ]
            if not candidates:
                self.candidate = None
            else:
                self.candidate = max(candidates, key = self.candidate_score)

    def display_fg(self, cr):
        for node in self.nodes:
            self.gui.highlight_node(cr, node, False)

    def previewed_equiv(self):
        return self.candidate

    def candidate_score(self, equiv):
        raise Exception("Not implemented by a subclass")
    def use_equiv(self, equiv):
        raise Exception("Not implemented by a subclass")

class JoinEquiv(LatticeStep):
    def candidate_score(self, equiv):
        return len(equiv.classes)
    def use_equiv(self, equiv):
        return self.gui.equivalence | equiv

class MeetEquiv(LatticeStep):
    def candidate_score(self, equiv):
        return -len(equiv.classes)
    def use_equiv(self, equiv):
        return self.gui.equivalence & equiv
