from openglider.airfoil import get_x_value
from openglider.plots import cuts, PlotPart
from openglider.plots.glider.config import PatternConfig
from openglider.vector import PolyLine2D, vector_angle
from openglider.vector.text import Text
import openglider.vector.projection as projection
from openglider.plots import DrawingArea


class PanelPlotMaker:
    DefaultConf = PatternConfig

    def __init__(self, cell, attachment_points=[], config=None):
        self.cell = cell
        self.attachment_points = [p for p in attachment_points if p.rib in self.cell.ribs]
        self.config = self.DefaultConf(config)

        self._flattened_cell = None

    def _get_flatten_cell(self):
        if self._flattened_cell is None:
            # assert isinstance(cell, Cell)
            left, right = projection.flatten_list(self.cell.prof1,
                                                         self.cell.prof2)
            left_bal = left.copy()
            right_bal = right.copy()
            ballooning = [self.cell.ballooning[x] for x in self.cell.rib1.profile_2d.x_values]
            for i in range(len(left)):
                diff = (right[i] - left[i]) * ballooning[i] / 2
                left_bal.data[i] -= diff
                right_bal.data[i] += diff

            inner = [left, right]
            ballooned = [left_bal, right_bal]

            outer_left = left_bal.copy().add_stuff(-self.config.allowance_general)
            outer_right = right_bal.copy().add_stuff(self.config.allowance_general)

            outer_orig = [outer_left, outer_right]
            outer = [l.copy().check() for l in outer_orig]

            self._flattened_cell = [
                inner,
                ballooned,
                outer,
                outer_orig
            ]

        return self._flattened_cell

    def get_panels(self):
        cell_panels = []
        flattened_cell = self._get_flatten_cell()

        for part_no, panel in enumerate(self.cell.panels):
            plot = PanelPlot(panel, self.cell, flattened_cell, self.config)
            dwg = plot.flatten(self.attachment_points)
            cell_panels.append(dwg)

        return DrawingArea.stack_column(cell_panels, self.config.patterns_align_dist_y)

    def get_dribs(self, attachment_points=None):
        dribs = []
        for drib in self.cell.diagonals:
            drib_plot = DribPlot(drib, self.cell, self.config)
            dribs.append(drib_plot.flatten(attachment_points))

        return dribs


class PanelPlot(object):
    DefaultConf = PanelPlotMaker.DefaultConf

    def __init__(self, panel, cell, flattended_cell, config):
        self.panel = panel
        self.cell = cell
        self.inner, self.ballooned, self.outer, self.outer_orig = flattended_cell
        self.config = self.DefaultConf(config)

        self.x_values = self.cell.rib1.profile_2d.x_values

    def flatten(self, attachment_points):
        plotpart = PlotPart(material_code=self.panel.material_code, name=self.panel.name)

        cut_allowances = {
            "folded": self.config.allowance_entry_open,
            "parallel": self.config.allowance_trailing_edge,
            "orthogonal": self.config.allowance_design
        }

        front_left = get_x_value(self.x_values, self.panel.cut_front["left"])
        back_left = get_x_value(self.x_values, self.panel.cut_back["left"])
        front_right = get_x_value(self.x_values, self.panel.cut_front["right"])
        back_right = get_x_value(self.x_values, self.panel.cut_back["right"])

        # allowance fallbacks
        allowance_front = cut_allowances[self.panel.cut_front["type"]]
        allowance_back = cut_allowances[self.panel.cut_back["type"]]

        # get allowance from self.panel
        amount_front = -self.panel.cut_front.get("amount", allowance_front)
        amount_back = self.panel.cut_back.get("amount", allowance_back)

        # cuts -> cut-line, index left, index right
        cut_front = cuts[self.panel.cut_front["type"]](
            [[self.ballooned[0], front_left],
             [self.ballooned[1], front_right]],
            self.outer[0], self.outer[1], amount_front)

        cut_back = cuts[self.panel.cut_back["type"]](
            [[self.ballooned[0], back_left],
             [self.ballooned[1], back_right]],
            self.outer[0], self.outer[1], amount_back)

        panel_left = self.outer[0][cut_front.index_left:cut_back.index_left]
        panel_back = cut_back.curve.copy()
        panel_right = self.outer[1][cut_front.index_right:cut_back.index_right:-1]
        panel_front = cut_front.curve.copy()

        # spitzer schnitt
        # rechts
        if cut_front.index_right >= cut_back.index_right:
            panel_right = PolyLine2D([])

            _cuts = panel_front.cut_with_polyline(panel_back, startpoint=len(panel_front)-1)
            try:
                ik_front, ik_back = next(_cuts)
                panel_back = panel_back[:ik_back]
                panel_front = panel_front[:ik_front]
            except StopIteration:
                pass  # todo: fix!!

        #lechts
        if cut_front.index_left >= cut_back.index_left:
            panel_left = PolyLine2D([])

            _cuts = panel_front.cut_with_polyline(panel_back, startpoint=0)
            try:
                ik_front, ik_back = next(_cuts)
                panel_back = panel_back[:ik_back]
                panel_front = panel_front[:ik_front]
            except StopIteration:
                pass  # todo: fix aswell!

        panel_back = panel_back[::-1]
        if panel_right:
            panel_right = panel_right[::-1]

        envelope = panel_right + panel_back + panel_left[::-1] + panel_front
        envelope += PolyLine2D([envelope[0]])

        plotpart.layers["envelope"].append(envelope)

        plotpart.layers["stitches"] += [
            self.ballooned[0][front_left:back_left],
            self.ballooned[1][front_right:back_right]]

        plotpart.layers["marks"] += [
            PolyLine2D([self.ballooned[0][front_left], self.ballooned[1][front_right]]),
            PolyLine2D([self.ballooned[0][back_left], self.ballooned[1][back_right]])]

        if False:
            if panel_right:
                right = PolyLine2D([panel_front.last()]) + panel_right + PolyLine2D([panel_back[0]])
                plotpart.layers["cuts"].append(right)

            plotpart.layers["cuts"].append(panel_back)

            if panel_left:
                left = PolyLine2D([panel_back.last()]) + panel_left + PolyLine2D([panel_front[0]])
                plotpart.layers["cuts"].append(left)

            plotpart.layers["cuts"].append(panel_front)
        else:
            plotpart.layers["cuts"].append(envelope.copy())

        self._insert_text(plotpart)
        self._insert_controlpoints(plotpart)
        self._insert_attachment_points(plotpart, attachment_points=attachment_points)

        self._align_upright(plotpart)

        return plotpart

    def get_point(self, x):
        ik = get_x_value(self.x_values, x)
        return [lst[ik] for lst in self.ballooned]

    def get_p1_p2(self, x, which):
        side = {"left": 0, "right": 1}[which]
        ik = get_x_value(self.x_values, x)

        return self.ballooned[side][ik], self.outer_orig[side][ik]

    def _align_upright(self, plotpart):
        side = "left"

        p1 = self.get_p1_p2(self.panel.cut_front[side], side)[0]
        p2 = self.get_p1_p2(self.panel.cut_back[side], side)[0]

        vector = p2 - p1
        angle = vector_angle(vector, [0, 1])
        plotpart.rotate(-angle)
        return plotpart

    def _insert_text(self, plotpart):
        left = get_x_value(self.x_values, self.panel.cut_front["left"])
        right = get_x_value(self.x_values, self.panel.cut_front["right"])
        text = self.panel.name
        part_text = Text(text,
                         self.ballooned[0][left],
                         self.ballooned[1][right],
                         size=self.config.allowance_design*0.8,
                         align="left",
                         valign=-0.5,
                         height=0.8).get_vectors()
        plotpart.layers["text"] += part_text

    def _insert_controlpoints(self, plotpart):
        for x in self.config.distribution_controlpoints:
            for side in ("left", "right"):
                if self.panel.cut_front[side] <= x <= self.panel.cut_back[side]:
                    p1, p2 = self.get_p1_p2(x, side)
                    plotpart.layers["L0"] += self.config.marks_laser_controlpoint(p1, p2)

    def _insert_attachment_points(self, plotpart, attachment_points):
        print("jo",  attachment_points)
        for attachment_point in attachment_points:
            if attachment_point.rib == self.cell.rib1:
                align = "left"
            elif attachment_point.rib == self.cell.rib2:
                align = "right"
            else:
                continue

            which = align

            if self.panel.cut_front[which] <= attachment_point.rib_pos <= self.panel.cut_back[which]:
                left, right = self.get_point(attachment_point.rib_pos)

                if self.config.insert_attachment_point_text:
                    plotpart.layers["text"] += Text(" {} ".format(attachment_point.name), left, right,
                                                    size=0.01,  # 1cm
                                                    align=align, valign=-0.5).get_vectors()

                p1, p2 = self.get_p1_p2(attachment_point.rib_pos, which)
                plotpart.layers["marks"] += self.config.marks_attachment_point(p1, p2)
                plotpart.layers["L0"] += self.config.marks_laser_attachment_point(p1, p2)




class DribPlot(object):
    DefaultConf = PanelPlotMaker.DefaultConf

    def __init__(self, drib, cell, config):
        self.drib = drib
        self.cell = cell
        self.config = self.DefaultConf(config)

        self._left, self._right = None, None
        self._left_out = self._right_out = None

    def _get_inner(self):
        if self._left is None:
            left, right = self.drib.get_flattened(self.cell)
            self._left = left
            self._right = right
        return self._left, self._right

    def _get_outer(self):
        if self._left_out is None:
            left, right = self._get_inner()
            left_out = left.copy()
            right_out = right.copy()

            left_out.add_stuff(-self.config.allowance_general)
            right_out.add_stuff(self.config.allowance_general)
            self._left_out = left_out
            self._right_out = right_out

        return self._left_out, self._right_out

    def get_left(self, x):
        return self.get_p1_p2(x, side=0)

    def get_right(self, x):
        return self.get_p1_p2(x, side=1)

    def _is_valid(self, x, side=0):
        if side == 0:
            front = self.drib.left_front
            back = self.drib.left_back
        else:
            front = self.drib.right_front
            back = self.drib.right_back

        if (front[1], back[1]) not in ((-1,-1), (1,1)):
            return False

        if front[1] > 0:
            # swapped sides
            boundary = [-front[0], -back[0]]
        else:
            boundary = [front[0], back[0]]
        boundary.sort()

        if not boundary[0] <= x <= boundary[1]:
            return False

        return True

    def get_p1_p2(self, x, side=0):
        assert self._is_valid(x, side=side)

        left, right = self._get_inner()
        left_out, right_out = self._get_outer()

        if side == 0:
            front = self.drib.left_front
            back = self.drib.left_back
            rib = self.cell.rib1
            inner = left
            outer = left_out
        else:
            front = self.drib.right_front
            back = self.drib.right_back
            rib = self.cell.rib2
            inner = right
            outer = right_out

        assert front[0] <= x <= back[0]

        foil = rib.profile_2d
        # -1 -> lower, 1 -> upper
        foil_side = 1 if front[1] == -1 else -1

        x1 = front[0] * foil_side
        x2 = x * foil_side

        ik_1 = foil(x1)
        ik_2 = foil(x2)
        length = foil[ik_1:ik_2].get_length() * rib.chord

        ik_new = inner.extend(0, length)
        return inner[ik_new], outer[ik_new]

    def _insert_attachment_points(self, plotpart, attachment_points=None):
        attachment_points = attachment_points or []

        for attachment_point in attachment_points:
            x = attachment_point.rib_pos
            if attachment_point.rib is self.cell.rib1:
                if not self._is_valid(x, side=0):
                    continue
                p1, p2 = self.get_left(attachment_point.rib_pos)
            elif attachment_point.rib is self.cell.rib2:
                if not self._is_valid(x, side=1):
                    continue

                p1, p2 = self.get_right(attachment_point.rib_pos)
            else:
                continue

            plotpart.layers["marks"] += self.config.marks_attachment_point(p1, p2)
            plotpart.layers["L0"] += self.config.marks_laser_attachment_point(p1, p2)

    def _insert_text(self, plotpart):
        left, right = self._get_inner()

        #text_p1 = left_out[0] + self.config.drib_text_position * (right_out[0] - left_out[0])
        text_p1 = left[0]
        plotpart.layers["text"] += Text(" {} ".format(self.drib.name),
                                        text_p1,
                                        right[0],
                                        size=self.config.drib_allowance_folds*0.8,
                                        height=0.8,
                                        valign=-0.5).get_vectors()

    def flatten(self, attachment_points=None):
        plotpart = PlotPart(material_code=self.drib.material_code, name=self.drib.name)
        left, right = self._get_inner()
        left_out, right_out = self._get_outer()

        if self.config.drib_num_folds > 0:
            alw2 = self.config.drib_allowance_folds
            cut_front = cuts["folded"]([[left, 0], [right, 0]],
                                       left_out,
                                       right_out,
                                       -alw2,
                                       num_folds=self.config.drib_num_folds)
            cut_back = cuts["folded"]([[left, len(left) - 1],
                                       [right, len(right) - 1]],
                                      left_out,
                                      right_out,
                                      alw2,
                                      num_folds=self.config.drib_num_folds)

        else:
            raise NotImplementedError



        # print("left", left_out[cut_front[1]:cut_back[1]].get_length())
        plotpart.layers["cuts"] += [left_out[cut_front.index_left:cut_back.index_left] +
                                    cut_back.curve +
                                    right_out[cut_front.index_right:cut_back.index_right:-1] +
                                    cut_front.curve[::-1]]

        plotpart.layers["marks"].append(PolyLine2D([left[0], right[0]]))
        plotpart.layers["marks"].append(PolyLine2D([left[len(left)-1], right[len(right)-1]]))


        #print(left, right)

        plotpart.layers["stitches"] += [left, right]

        self._insert_attachment_points(plotpart, attachment_points)
        self._insert_text(plotpart)

        return plotpart

