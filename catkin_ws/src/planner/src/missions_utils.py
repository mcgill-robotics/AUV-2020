COMPETITION_TASKS = ["Gate", "Trick", "Lane Marker", "Buoy", "Lane Marker"]
QUALIFYING_TASKS = ["Quali"]


def get_mission_index(mission_options, mission_name):
     """
     Returns the index of given mission name in mission options.
     """
     mission_index = [
          option[0] == mission_name for option in mission_options
     ].index(True)
     return mission_index

def get_user_missions_selected(mission_options):
     """
     Returns missions selected by user (including pre-made missions).
     """
     # Print Mission Options.
     for i in range(len(mission_options)):
          print(" > [{}] ".format(i+1) + mission_options[i][0])
     
     # Check if all selected options are valid.
     is_answer_valid = False
     while not is_answer_valid:
          missions_selected = list(map(int, input("Select missions (separated by comma [1,2,3]): ").split(",")))
          # User selection starts from index 1. Move indexes back by 1. 
          missions_selected = [x - 1 for x in missions_selected]
          if len(missions_selected) > 0 and all(0 <= selected < len(mission_options) for selected in missions_selected):
               is_answer_valid = True
          else:
               print("Invalid answer!!!")

     # If a pre-made mission was selected, overwrite missions_selected with the correspding mission tasks.
     if get_mission_index(mission_options, "Competition") in missions_selected:
          missions_selected = [get_mission_index(mission_options, task) for task in COMPETITION_TASKS]
     elif get_mission_index(mission_options, "Quali") in missions_selected:
          missions_selected = [get_mission_index(mission_options, task) for task in QUALIFYING_TASKS]

     return missions_selected

def get_state_params(mission_options, missions_selected, index):
     # increment num of times the user has selected this task.
     mission_options[missions_selected[index]][3] += 1
     current_mission_name = mission_options[missions_selected[index]][2]
     current_mission_count = mission_options[missions_selected[index]][3]
     # if last mission: no mission after.
     # else: get state name of next mission.
     if index == len(missions_selected) - 1:
          mission_after = None
     else:
          next_mission_selected = missions_selected[index + 1]
          mission_after = mission_options[next_mission_selected][2] + str(mission_options[next_mission_selected][3] + 1)
     
     return current_mission_name, current_mission_count, mission_after


# Automatically import all functions and constants.
__all__ = [name for name in globals() if not name.startswith('__')]