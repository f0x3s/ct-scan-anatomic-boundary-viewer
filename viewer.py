import os
import pydicom
import dicom2jpg
import cv2
import numpy as np

master_folder_path = "./dicoms"

class colors:
    PURPLE = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    ENDC = '\033[0m'

# non recursive function to list all folders in a given path
def list_folders(path):
    
    folders = []

    print(f"searching for dicom series in {path}...")

    for item in os.scandir(path):
        if item.is_dir():
            print(f"found: {item.name}")

            folders.append((item.name, item.path))

    return folders

# check if the user selected series number is valid
def validate_user_selected_series(series_number, dicom_series_paths):
    if series_number < 1 or series_number > len(dicom_series_paths):
        raise ValueError(f"Invalid series number. Please enter a number between 1 and {len(dicom_series_paths)}.")

def main():

    # identify all dicom series in the master folder
    dicom_series_paths = list_folders(master_folder_path)

    print(f"\n{colors.PURPLE}{len(dicom_series_paths)} dicom series are available to view: {colors.ENDC}")

    for item in range(len(dicom_series_paths)):
        print(f"{colors.BLUE}    ({item + 1}) {dicom_series_paths[item][0]}{colors.ENDC}")

    print(f"\n{colors.PURPLE}Enter the number of the dicom series you want to view: {colors.ENDC}")

    while(True):
        try:
            series_number = int(input())

            validate_user_selected_series(series_number, dicom_series_paths)
    
            break
            
        except ValueError as e:
            print(f"{colors.RED}Error: {e}{colors.ENDC}")

if __name__ == "__main__":
    main()
