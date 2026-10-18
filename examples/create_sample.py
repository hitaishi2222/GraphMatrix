"""Create a small sample project for trying GraphMatrix."""

import numpy as np
from graphmatrix.core.model import Project
from graphmatrix.core.scripting.api import GraphMatrixAPI
from graphmatrix.core.commands import CommandStack

project = Project("Sample")
api = GraphMatrixAPI(project, CommandStack())
book = api.add_workbook("Book1")
sheet = api.add_worksheet("Book1", "Sheet1")
x = np.linspace(0, 2 * np.pi, 200)
api.add_column("Book1/Sheet1", "X", "X", data=x.tolist(), units="rad")
api.add_column("Book1/Sheet1", "Y", "Y", data=np.sin(x).tolist(), comment="sin(x)")
api.add_graph("Graph1", source="Book1/Sheet1", x="X", y="Y")
project.save("sample.rsproj")
print("Wrote sample.rsproj")
