# ! /usr/bin/python2
# -*- coding: utf-8; -*-
#
# (c) 2013 booya (http://booya.at)
#
# This file is part of the OpenGlider project.
#
# OpenGlider is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# OpenGlider is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OpenGlider.  If not, see <http://www.gnu.org/licenses/>.
import svgwrite

from openglider.airfoil import get_x_value
from openglider.plots.marks import triangle, line
import projection
# from openglider.glider import Glider
# from openglider.glider.cell import Cell
from cuts import cuts
from .part import PlotPart
from openglider.vector import Vectorlist2D, depth


# Sign configuration
sewing_config = {
    "marks": {
        "attachment-point": lambda p1, p2: marks.triangle(2 * p1 - p2, p1),  # on the inner-side
        "panel-cut": marks.line
    },
    "allowance_general": 0.01,
    "scale": 1000,
    "layers":
        {"OUTER_CUTS": {
            "id": 'outer',
            "stroke_width": "1",
            "stroke": "green",
            "fill": "none"},
         "SEWING_MARKS": {
             "id": 'marks',
             "stroke_width": "1",
             "stroke": "black",
             "fill": "none"},
         "TEXT": {
             "id": 'text',
             "stroke_width": "1",
             "stroke": "black",
             "fill": "none"},
        }


}


def flattened_cell(cell):
    # assert isinstance(cell, Cell)
    left, right = projection.flatten_list(cell.prof1, cell.prof2)
    left_bal = left.copy()
    right_bal = right.copy()
    ballooning_left = [cell.rib1.ballooning[x] for x in cell.rib1.profile_2d.x_values]
    ballooning_right = [cell.rib2.ballooning[x] for x in cell.rib2.profile_2d.x_values]
    for i in range(len(left)):
        diff = right[i] - left[i]
        left_bal.data[i] -= diff * ballooning_left[i]
        right_bal.data[i] += diff * ballooning_right[i]
    return left_bal, left, right, right_bal


def flatten_glider(glider):
    # assert isinstance(glider, Glider)
    parts = []
    xvalues = glider.profile_x_values
    #cuts = openglider.plots.cuts
    for cell in glider.cells:
        left_bal, left, right, right_bal = flattened_cell(cell)
        left_out = left_bal.copy()
        right_out = right_bal.copy()
        left_out.add_stuff(-sewing_config["allowance_general"])
        right_out.add_stuff(sewing_config["allowance_general"])
        for panel in cell.panels:
            front_left = get_x_value(xvalues, panel.cut_front[0])
            back_left = get_x_value(xvalues, panel.cut_back[0])
            front_right = get_x_value(xvalues, panel.cut_front[1])
            back_right = get_x_value(xvalues, panel.cut_back[1])
            cut_front = cuts[panel.cut_front[2] - 1]([[left_bal, front_left],
                                                      [right_bal, front_right]],
                                                     left_out, right_out, -panel.cut_front[3])
            cut_back = cuts[panel.cut_back[2] - 1]([[left_bal, back_left],
                                                    [right_bal, back_right]],
                                                   left_out, right_out, panel.cut_back[3])
            part_cuts = [left_out[cut_front[1]:cut_back[1]] +
                         Vectorlist2D(cut_back[0]) +
                         right_out[cut_front[2]:cut_back[2]:-1] +
                         Vectorlist2D(cut_front[0])[::-1]]
            part_marks = [left_bal[front_left:back_left] +
                          right_bal[front_right:back_right:-1] +
                          Vectorlist2D([left_bal[front_left]])]
            part_text = []

            for attachment_point in filter(lambda p: p.rib is cell.rib1, glider.attachment_points):
                pass




            parts.append(PlotPart({"OUTER_CUTS": part_cuts,
                                   "SEWING_MARKS": part_marks,
                                   #"TEXT": part_text
            }))

    ##################################RIBS###########################
    #################################################################
    for i, rib in enumerate(glider.ribs[glider.has_center_cell:-1]):
        rib_no = i + glider.has_center_cell
        profile = rib.profile_2d.copy()
        chord = rib.chord
        profile.scale(chord)
        profile_outer = profile.copy()
        profile_outer.add_stuff(0.01)

        def return_points(x_value):
            ik = get_x_value(xvalues, x_value)
            return profile[ik], profile_outer[ik]

        rib_marks = []

        #####################marks for attachment-points##################################
        attachment_points = filter(lambda p: p.rib == rib, glider.attachment_points)
        for point in attachment_points:
            rib_marks += sewing_config["marks"]["attachment-point"](*return_points(point.rib_pos))

        #####################marks for panel-cuts#########################################
        rib_cuts = set()
        if rib_no > 0:
            for panel in glider.cells[rib_no - 1].panels:
                rib_cuts.add(panel.cut_front[1])  # left cell
                rib_cuts.add(panel.cut_back[1])
        for panel in glider.cells[rib_no].panels:
            rib_cuts.add(panel.cut_front[0])
            rib_cuts.add(panel.cut_back[0])
        rib_cuts.remove(1)
        rib_cuts.remove(-1)
        for cut in rib_cuts:
            rib_marks += sewing_config["marks"]["panel-cut"](*return_points(cut))

        #####################general marks################################################

        #add text, entry, holes

        profile_outer.close()
        parts.append(PlotPart({"OUTER_CUTS": [profile_outer],
                               "SEWING_MARKS": [profile] + rib_marks}))

    return parts


def create_svg(partlist, path):
    drawing = svgwrite.Drawing()
    # partlist = [partlist[1]]
    max_last = [0, 0]
    for part in partlist:
        part_group = svgwrite.container.Group()
        part.shift([max_last[0] - part.min_x + 0.2, max_last[1] - part.max_y])

        for layer_name, layer_config in sewing_config["layers"].iteritems():
            if layer_name in part.layer_dict:
                max_last[0] = part.max_x
                lines = part.return_layer_svg(layer_name, scale=sewing_config["scale"])
                for line in lines:
                    element = svgwrite.shapes.Polyline(line, **layer_config)
                    part_group.add(element)
            drawing.add(part_group)

    with open(path, "w") as output_file:
        return drawing.write(output_file)

        # FLATTENING
        # Dict for layers
        # Flatten all cell-parts
        #   * attachment points
        #   * miniribs
        #   * sewing marks
        # FLATTEN RIBS
        #   * airfoil
        #   * attachment points
        #   * gibus arcs
        #   * holes
        #   * rigidfoils
        #   * sewing marks
        #   ---> SCALE
        # FLATTEN DIAGONALS
        #     * Flatten + add stuff
        #     * Draw marks on ribs