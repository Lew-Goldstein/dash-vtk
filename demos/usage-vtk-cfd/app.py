import dash
import dash_vtk
import dash_bootstrap_components as dbc
import dash_html_components as html
import dash_core_components as dcc
from dash.dependencies import Input, Output, State

import vtk
import pyvista as pv
import numpy as np
from vtk.util.numpy_support import vtk_to_numpy

import os
import random

from color_maps import presets

def toDropOption(name):
    return { 'label': name, 'value': name}

# -----------------------------------------------------------------------------
# VTK Pipeline
# -----------------------------------------------------------------------------

# Figure out file path to load
data_basedir = os.path.join(os.path.dirname(__file__), 'data')
bike_filename = os.path.join(data_basedir, 'bike.vtp')
tunnel_filename = os.path.join(data_basedir, 'tunnel.vtu')

# Seed positions
point1 = [-0.4, 0, 0.05]
point2 = [-0.4, 0, 1.5]

# VTK Pipeline setup
bikeReader = vtk.vtkXMLPolyDataReader()
bikeReader.SetFileName(bike_filename)
bikeReader.Update()

tunnelReader = vtk.vtkXMLUnstructuredGridReader()
tunnelReader.SetFileName(tunnel_filename)
tunnelReader.Update()

lineSeed = vtk.vtkLineSource()
lineSeed.SetPoint1(*point1)
lineSeed.SetPoint2(*point2)
lineSeed.SetResolution(50)

streamTracer = vtk.vtkStreamTracer()
streamTracer.SetInputConnection(tunnelReader.GetOutputPort())
streamTracer.SetSourceConnection(lineSeed.GetOutputPort())
streamTracer.SetIntegrationDirectionToForward()
streamTracer.SetIntegratorTypeToRungeKutta45()
streamTracer.SetMaximumPropagation(3)
streamTracer.SetIntegrationStepUnit(2)
streamTracer.SetInitialIntegrationStep(0.2)
streamTracer.SetMinimumIntegrationStep(0.01)
streamTracer.SetMaximumIntegrationStep(0.5)
streamTracer.SetMaximumError(0.000001)
streamTracer.SetMaximumNumberOfSteps(2000)
streamTracer.SetTerminalSpeed(0.00000000001)

tubeFilter = vtk.vtkTubeFilter()
tubeFilter.SetInputConnection(streamTracer.GetOutputPort())
tubeFilter.SetRadius(0.01)
tubeFilter.SetNumberOfSides(6)
tubeFilter.CappingOn()
tubeFilter.Update()

streamsPolyData = pv.wrap(streamTracer.GetOutput())
streamsPoints = streamsPolyData.points.ravel()
streamsLines = vtk_to_numpy(streamsPolyData.GetLines().GetData())

def updateTubesGeometry(field_name):
    tubeFilter.Update()
    tubesPolyData = pv.wrap(tubeFilter.GetOutput())
    tubesPoints = tubesPolyData.points.ravel()
    tubesPolys = vtk_to_numpy(tubesPolyData.GetPolys().GetData())
    tubesStrips = vtk_to_numpy(tubesPolyData.GetStrips().GetData())
    colorByArray = tubesPolyData.GetPointData().GetArray(field_name)
    colorRange = colorByArray.GetRange(-1)
    nbComponents = colorByArray.GetNumberOfComponents()

    return [tubesPoints, tubesPolys, tubesStrips, vtk_to_numpy(colorByArray).ravel(), nbComponents, colorRange]

tubesPoints, tubesPolys, tubesStrips, field, nb_components, color_range = updateTubesGeometry('p')

bikePolyData = pv.wrap(bikeReader.GetOutput())
bikePoints = bikePolyData.points.ravel()
bikePolys = vtk_to_numpy(bikePolyData.GetPolys().GetData())

# -----------------------------------------------------------------------------
# GUI setup
# -----------------------------------------------------------------------------

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server

vtk_view = dash_vtk.View(
    id="vtk-view",
    children=[
        dash_vtk.GeometryRepresentation(
            id="bike-rep",
            children=[
                dash_vtk.PolyData(
                    id="bike-polydata",
                    points=bikePoints,
                    polys=bikePolys,
                )
            ],
        ),
        dash_vtk.GeometryRepresentation(
            id="tubes-rep",
            colorMapPreset="erdc_rainbow_bright",
            colorDataRange=color_range,
            children=[
                dash_vtk.PolyData(
                    id="tubes-polydata",
                    points=tubesPoints,
                    polys=tubesPolys,
                    strips=tubesStrips,
                    children=[
                        dash_vtk.PointData([
                            dash_vtk.DataArray(
                                id="data-array",
                                registration="setScalars",
                                values=field,
                                numberOfComponents=nb_components,
                            )
                        ])
                    ],
                )
            ],
        ),
        dash_vtk.GeometryRepresentation(
            id="seed-rep",
            property={
                'color': [0.8, 0, 0],
                'representation': 0,
                'pointSize': 8,
            },
            children=[
                dash_vtk.Algorithm(
                    id="seed-line",
                    vtkClass="vtkLineSource",
                    state={'point1': point1, 'point2': point2 },
                )
            ],
        )
    ]
)

controls = dbc.Col(children=[
    dbc.Card(
        [
            dbc.CardHeader("Seeds"),
            dbc.CardBody(
                [
                    html.P("Seed line:"),
                    dcc.Slider(
                        id="point-1",
                        min=-1,
                        max=1,
                        step=0.01,
                        value=0,
                        marks={-1: "-1", 1: "+1"},
                    ),
                    dcc.Slider(
                        id="point-2",
                        min=-1,
                        max=1,
                        step=0.01,
                        value=0,
                        marks={-1: "-1", 1: "+1"},
                    ),
                    html.Br(),
                    html.P("Line resolution:"),
                    dcc.Slider(
                        id="seed-resolution",
                        min=5,
                        max=50,
                        step=1,
                        value=10,
                        marks={5: "5", 50: "50"},
                    ),
                ]
            ),
        ]
    ),
    dbc.Card(
        [
            dbc.CardHeader("Color By"),
            dbc.CardBody(
                [
                    html.P("Field name"),
                    dcc.Dropdown(
                        id="color-by",
                        options=[
                            {'label': 'p', 'value': 'p'},
                            {'label': 'Rotation', 'value': 'Rotation'},
                            {'label': 'U', 'value': 'U'},
                            {'label': 'Vorticity', 'value': 'Vorticity'},
                            {'label': 'k', 'value': 'k'},
                        ],
                        value="p"
                    ),
                    html.Br(),
                    html.P("Color Preset"),
                    dcc.Dropdown(
                        id="preset",
                        options=list(map(toDropOption, presets)),
                        value="erdc_rainbow_bright",
                    ),
                ]
            ),
        ]
    ),
])


app.layout = dbc.Container(
    fluid=True,
    children=[
        html.H1("Demo of dash_vtk.CFD"),
        html.Hr(),
        dbc.Row(
            [
                dbc.Col(
                    width=4,
                    children=[controls],
                ),
                dbc.Col(
                    width=8,
                    children=[
                        html.Div(
                            vtk_view,
                            style={"height": "calc(80vh - 20px)", "width": "100%"},
                        )
                    ],
                ),
            ]
        ),
    ],
)

# -----------------------------------------------------------------------------
# Handle seeds
# -----------------------------------------------------------------------------

@app.callback(
    [Output("seed-line", "state"),
     Output("tubes-polydata", "points"),
     Output("tubes-polydata", "polys"),
     Output("tubes-polydata", "strips"),
     Output("data-array", "values"),
     Output("data-array", "numberOfComponents"),
     Output("tubes-rep", "colorDataRange"),
     Output("tubes-rep", "colorMapPreset"),
     Output("vtk-view", "triggerRender")],
    [Input("point-1", "value"),
     Input("point-2", "value"),
     Input("seed-resolution", "value"),
     Input("color-by", "value"),
     Input("preset", "value")],
)
def update_seeds(y1, y2, resolution, colorByField, presetName):
    point1[1] = y1
    point2[1] = y2

    lineSeed.SetPoint1(*point1)
    lineSeed.SetPoint2(*point2)
    lineSeed.SetResolution(resolution)

    tubesPoints, tubesPolys, tubesStrips, field, nb_comps, colorRange = updateTubesGeometry(
        colorByField)

    return [
        {"point1": point1, "point2": point2, "resolution": resolution},
        tubesPoints,
        tubesPolys,
        tubesStrips,
        field,
        nb_comps,
        colorRange,
        presetName,
        random.random(),
    ]

# -----------------------------------------------------------------------------

if __name__ == "__main__":
    app.run_server(debug=True)