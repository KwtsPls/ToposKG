import os
import inspect

def get_relative_path(relative_path):
    """
    Get the relative path of the current script.
    """
    caller_frame = inspect.stack()[1]
    caller_filepath = caller_frame.filename

    caller_dir = os.path.dirname(os.path.abspath(caller_filepath))
    data_path = os.path.join(caller_dir, relative_path)
    return data_path