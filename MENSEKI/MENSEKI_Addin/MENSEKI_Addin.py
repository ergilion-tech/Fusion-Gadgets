#FusionAPI_python_Addin MENSEKI_Addin
#Author-kantoku
#Description-

#using Fusion360AddinSkeleton
#https://github.com/tapnair/Fusion360AddinSkeleton
#Special thanks:Patrick Rainsberry

import adsk.core
from .Fusion360Utilities.Fusion360CommandBase import Fusion360CommandBase
from .Fusion360Utilities.Fusion360Utilities import AppObjects
from .total_area import total_area
from .total_volume import total_volume
from .total_length import total_length

commands = []
command_definitions = []

# Set to True to display various useful messages when debugging your app
debug = False

def run(context):

    # Length
    cmd = {
        'cmd_name': 'Length',
        'cmd_description': 'Total length of selected edges',
        'cmd_id': 'total_length_id',
        'cmd_resources': './resources/total_length',
        'workspace': 'FusionSolidEnvironment',
        'toolbar_panel_id': 'InspectPanel',
        'class': total_length
    }
    command_definitions.append(cmd)

    # Area
    cmd = {
        'cmd_name': 'Area',
        'cmd_description': 'Total area of selected faces',
        'cmd_id': 'total_area_id',
        'cmd_resources': './resources/total_area',
        'workspace': 'FusionSolidEnvironment',
        'toolbar_panel_id': 'InspectPanel',
        'class': total_area
    }
    command_definitions.append(cmd)

    # Volume
    cmd = {
        'cmd_name': 'Volume',
        'cmd_description': 'Total volume of selected bodies',
        'cmd_id': 'total_volume_id',
        'cmd_resources': './resources/total_volume',
        'workspace': 'FusionSolidEnvironment',
        'toolbar_panel_id': 'InspectPanel',
        'class': total_volume
    }
    command_definitions.append(cmd)

    # Don't change anything below here:
    for cmd_def in command_definitions:
        command = cmd_def['class'](cmd_def, debug)
        commands.append(command)

        for run_command in commands:
            run_command.on_run()


def stop(context):
    for stop_command in commands:
        stop_command.on_stop()
