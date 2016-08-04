from openglider.utils import Config
from openglider.physics.base import GliderCase
from openglider.physics.flow import GliderPanelMethod
from openglider.mesh import Mesh, Vertex

import paraFEM
from paraEigen import vector3


class GliderFemCase(GliderCase):
    class DefaultConf(GliderCase.DefaultConf):
        fem_timestep = 1.e-06
        fem_steps = 100000
        fem_output = 100

        # material properties
        rib_elasticity = 3000
        rib_nue = 0.3
        rib_rho = 0.01

        hull_elasticity = 3000
        hull_nue = 0.3
        hull_rho = 0.01

        line_elasticity = 5000
        line_rho = 0.01

        d_velocity = 0.1
        pressure_ramp = 20000     # steps for linear pressure ramp
        caseType = "line_forces"
        line_numpoints = 2
        vtk_fem_output = "/tmp/Fem/output"

    def __init__(self, glider, config=None, flow_case=None):
        super(GliderFemCase, self).__init__(glider, config)
        self.config = self.DefaultConf(config)
        if not self.config.symmetric_case:
            self.glider = glider.copy_complete()
        else:
            self.glider = glider
        self.flow_case = flow_case or GliderPanelMethod(glider, config)
        self.mesh = None
        self.case = None

    def run(self):
        if not self.flow_case.result:
            self.flow_case.run()
            self.flow_case.export_vtk("/tmp/flow")

        mesh = self.get_mesh()
        pressure = list(self.flow_case.pressure)
        vertices, polygons, boundary = mesh.get_indexed()

        rib_material = paraFEM.MembraneMaterial(self.config.rib_elasticity,
                                                self.config.rib_nue)
        rib_material.d_velocity = self.config.d_velocity
        rib_material.d_structural = 0.0
        rib_material.rho = self.config.rib_rho

        hull_material = paraFEM.MembraneMaterial(self.config.hull_elasticity,
                                                 self.config.hull_nue)
        hull_material.d_velocity = self.config.d_velocity
        hull_material.d_structural = 0.0
        hull_material.rho = self.config.hull_rho

        truss_material = paraFEM.TrussMaterial(self.config.line_elasticity)
        truss_material.d_velocity = 0.001
        truss_material.d_structural = 0
        truss_material.rho = self.config.line_rho

        nodes = [paraFEM.Node(*vertex) for vertex in vertices]

        if self.config.symmetric_case:
            for node in nodes:
                if node.position.y < 0.000001:
                    if abs(node.position.y) < 0.000001:
                        node.fixed.y = 0
                        if self.glider.has_center_cell:
                            pass # apply force constraint to get the influence of the other side on a rib
                    else:
                        pass # apply a symmetrical position constraint

        if self.config.caseType == "full":
            for index in boundary["lower_attachment_points"]:
                nodes[index].fixed = vector3(0, 0, 0)
        elif self.config.caseType == "line_forces":
            for index in boundary["lines"]:
                nodes[index].fixed = vector3(0, 0, 0)
        elements = []

        for i, polygon in enumerate(polygons["lines"]):
            poly_nodes = [nodes[index] for index in polygon]
            element = paraFEM.Truss(poly_nodes, truss_material)
            elements.append(element)

        for i, polygon in enumerate(polygons["hull"]):
            poly_nodes = [nodes[index] for index in polygon]
            # TODO: use a basic membrane constructor (paraFEM)
            if len(poly_nodes) == 3:
                element = paraFEM.Membrane3(poly_nodes, hull_material)
                element.setConstPressure(pressure[i])
                elements.append(element)
            elif len(poly_nodes) == 4:
                element = paraFEM.Membrane4(poly_nodes, hull_material, False)
                element.setConstPressure(pressure[i])
                elements.append(element)

        for i, polygon in enumerate(polygons["ribs"]):
            poly_nodes = [nodes[index] for index in polygon]
            if len(poly_nodes) == 3:
                element = paraFEM.Membrane3(poly_nodes, rib_material)
                elements.append(element)
            elif len(poly_nodes) == 4:
                element = paraFEM.Membrane4(poly_nodes, rib_material)
                elements.append(element)
        self.case = paraFEM.Case(elements)
        self.writer = paraFEM.vtkWriter(self.config.vtk_fem_output)

        write_interval = self.config.fem_steps // self.config.fem_output or 1
        p_ramp = self.config.pressure_ramp
        for i in range(self.config.fem_steps):
            ramp = 1 - (i < p_ramp) * (1 - float(i) / p_ramp)
            self.case.explicitStep(self.config.fem_timestep, ramp)
            if (i % write_interval) == 0:
                print(int(i / write_interval))
                self.writer.writeCase(self.case, 0.)
        if self.config.caseType == "line_forces":
            pass # store the line forces


    def get_mesh(self):
        if self.mesh:
            return self.mesh
        else:
            self.glider = self.flow_case.glider
            self.mesh = self.flow_case.mesh
        start = 0
        if (self.config.symmetric_case and self.glider.has_center_cell):
            start = 1
        for rib in self.glider.ribs[start:]:
            self.mesh += Mesh.from_rib(rib)

        if self.config.caseType == "line_forces":
            print("add uppermost lines to mesh")
            self.mesh += self.glider.lineset.get_upper_line_mesh(self.config.line_numpoints)

        if self.config.caseType == "full":
            print("add lines")
            self.mesh += self.glider.lineset.get_mesh(self.config.line_numpoints)

        self.mesh.delete_duplicates()
        return self.mesh
