import os
import pydicom
import dicom2jpg
import cv2
import numpy as np

master_folder_path = "./dicoms"

WINDOW_NAME = "DICOM Viewer"

# used for printing colors in terminal
class colors:
    PURPLE = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    ENDC = '\033[0m'

# list all folders in a given path root
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

# check if the user input is valid  for yes or no
def validate_user_yes_or_no(user_input):

    user_input = user_input.strip().lower()

    if user_input not in ["y", "n", "yes", "no"]:
        raise ValueError("Invalid input. Please enter 'y' or 'n'.")

    return "y" if user_input in ["y", "yes"] else "n"

# fetches all dicom files in given path and sorts by slice positon
# returnds a list of dicom files
def collate_dicom_files(series_path):

    dicom_files = []

    print("Building series...")

    for item in os.scandir(series_path):
        if item.is_file() and item.name.endswith(".dcm"):
            print("found: " + item.name)
            dicom_files.append(item)

    def slice_position(dicom):
        dataset = pydicom.dcmread(dicom.path, stop_before_pixels=True)
        return float(dataset.ImagePositionPatient[2])

    dicom_files.sort(key=slice_position)

    return dicom_files

# builds a list of tuples containing the dicom image and the dicom pixel datafor each dicom file in the series
# (<display image>, <pixel data>)
def process_dicom_files(dicom_files):

    dicoms = []

    for item in dicom_files:

        # load dicom file
        dicom = pydicom.dcmread(item)

        # builds a numpy array of the data for easy diplay (scaling data to 0-255)
        # dicom2jpg used because it is simpler for creating a viewable image than using pydicom and cv2 directly
        image = dicom2jpg.dicom2img(item.path)

        # builds a numpy array of the dicom pixel data for calculations (scaled to Hounsfield Units)
        hu_array = dicom.pixel_array * dicom.RescaleSlope + dicom.RescaleIntercept

        dicoms.append((image, hu_array))

        print(f"processed: {item.name}")

    return dicoms

def update_display(val):
    slice_index = cv2.getTrackbarPos("Slice", WINDOW_NAME)

    cv2.imshow(WINDOW_NAME, dicoms[slice_index][0])


def main():

    # this ahs to be global so that the update_display function can access it
    global dicoms

    print(f"{colors.PURPLE}Welcome to the DICOM Viewer!{colors.ENDC}")

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

    series = dicom_series_paths[series_number - 1]

    print(f"\n{colors.GREEN}You selected: {series[0]}{colors.ENDC}")

    dicoms = process_dicom_files(collate_dicom_files(series[1]))

    print(f"\n{colors.PURPLE}Found {len(dicoms)-1} dicom images in the selected series. Proceed? (y/n){colors.ENDC}")

    while(True):
        try: 
            user_choice = validate_user_yes_or_no(input())

            if user_choice == "y":
                break

            elif user_choice == "n":
                print(f"{colors.RED}Exiting program...{colors.ENDC}")
                exit()

        except ValueError as e:
                print(f"{colors.RED}Error: {e}{colors.ENDC}")


    # build openCV window
    cv2.namedWindow(WINDOW_NAME)

    cv2.createTrackbar(
        "Slice",
        WINDOW_NAME,
        round(len(dicoms)/2.0),
        len(dicoms) - 1,
        update_display
    )

    # wait for esc key to be pressed to exit the program
    while True:
        if cv2.waitKey(1) & 0xFF == 27:
            break



if __name__ == "__main__":
    main()
