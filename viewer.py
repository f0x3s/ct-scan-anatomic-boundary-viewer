import os
import pydicom
import dicom2jpg
import cv2
import numpy as np
from pathlib import Path
import shutil


master_folder_path = Path("./dicoms")

WINDOW_NAME = "DICOM Viewer"
current_display_image = None
region_of_interest = 0

EDGE_COLOR = (50, 0, 255)
REGION_COLOR = (128, 255, 10)

# used for printing colors in terminal
# using a class instead of a dictionary because it is easier to access the values without having to use quotes
class Colors:
    PURPLE = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    ENDC = '\033[0m'

# list containing the names and Hounsfield Unit ranges for various anatomical structures
# https://en.wikipedia.org/wiki/Hounsfield_scale
anatomy = [
    ("None", (None, None)),
    ("Air", (-1000, -500)),
    ("Fat", (-100, -60)),
    ("Water", (-5, 5)),
    ("Soft Tissue", (25, 60)),
    ("Bone", (300, 3000)),
    ("Metal", (3000, 10000))
]

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
    try:
        series_number = int(series_number)
    except ValueError:
        raise ValueError("Series number must be an integer")

    if series_number < 1 or series_number > len(dicom_series_paths):
        raise ValueError(
            f"Invalid series number. Please enter a number between 1 and {len(dicom_series_paths)}."
        )

    return series_number
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

    # extract the slice position from a DICOM file.
    # this is only valid for dicoms where the slice position varies along the z-axis (towards and away from head of patient)
    def slice_position(dicom):
        dataset = pydicom.dcmread(dicom.path, stop_before_pixels=True)
        return float(dataset.ImagePositionPatient[2])

    # i found that the test datasets i was using werent sorted by slice position...
    dicom_files.sort(key=slice_position)

    return dicom_files

# builds a list of tuples:
# (<display image>, <pixel data>, <slice position>, <patient id>)
def process_dicom_files(dicom_files):

    dcms = []

    for item in dicom_files:

        # load dicom file
        dicom = pydicom.dcmread(item)

        # builds a numpy array of the data for easy diplay (scaling data to 0-255)
        # dicom2jpg used because it is simpler for creating a viewable image than using pydicom and cv2 directly
        image = dicom2jpg.dicom2img(item.path)

        # builds a numpy array of the dicom pixel data for calculations (scaled to Hounsfield Units)
        hu_array = dicom.pixel_array * dicom.RescaleSlope + dicom.RescaleIntercept

        dcms.append((image, hu_array, dicom.ImagePositionPatient[2], dicom.PatientID))

        print(f"processed: {item.name}")

    return dcms

def threshold_data(data, region) :

    # create a new array to hold the thresholded data of same shape as the original data, but with a data type of uint8 (0-255)
    thresh = np.zeros(data.shape, dtype=np.uint8)

    min_hu, max_hu = anatomy[region][1]

    for y, row in enumerate(data) :
        for x, pixel in enumerate(row) :
            thresh[y][x] = 255 if (pixel > min_hu)and (pixel < max_hu) else 0

    return thresh


def march_squares(binary_data, output_image, downsample):

    edge_image = np.zeros(output_image.shape, dtype=np.uint8)
    cells = check_cells(binary_data)
    segments = lookup(cells, downsample)

    for point_1, point_2 in segments:
        cv2.line(
            edge_image,
            point_1,
            point_2,
            EDGE_COLOR,
            1
        )

    return edge_image

def check_cells(image) :

    grid = image.copy()
    height, width = grid.shape[:2]

    cells = []

    for y in range(height-1) :
        for x in range(width-1) :

            sub_grid = []

            for sub_y in [0,1] :
                for sub_x in [0,1] :
                    corner = 1 if grid[y + sub_y][x + sub_x] == 255 else 0
                    sub_grid.append(corner)

            cells.append((x,y,sub_grid))

    return cells

def lookup(cells, downsample) :
    half = downsample // 2

    edge_midpoints = {
        "top":    (half, 0),
        "right":  (downsample, half),
        "bottom": (half, downsample),
        "left":   (0, half),
    }

    segments = []

    for x, y, corners in cells:
        case = int("".join(str(corner) for corner in corners), 2)

        origin_x = x * downsample
        origin_y = y * downsample

        if case == 1 or case == 14:
            point_1 = (
                origin_x + edge_midpoints["bottom"][0],
                origin_y + edge_midpoints["bottom"][1]
            )
            point_2 = (
                origin_x + edge_midpoints["right"][0],
                origin_y + edge_midpoints["right"][1]
            )
            segments.append((point_1, point_2))

        if case == 2 or case == 13:
            point_1 = (
                origin_x + edge_midpoints["left"][0],
                origin_y + edge_midpoints["left"][1]
            )
            point_2 = (
                origin_x + edge_midpoints["bottom"][0],
                origin_y + edge_midpoints["bottom"][1]
            )
            segments.append((point_1, point_2))

        if case == 3 or case == 12:
            point_1 = (
                origin_x + edge_midpoints["left"][0],
                origin_y + edge_midpoints["left"][1]
            )
            point_2 = (
                origin_x + edge_midpoints["right"][0],
                origin_y + edge_midpoints["right"][1]
            )
            segments.append((point_1, point_2))

        if case == 4 or case == 11:
            point_1 = (
                origin_x + edge_midpoints["top"][0],
                origin_y + edge_midpoints["top"][1]
            )
            point_2 = (
                origin_x + edge_midpoints["right"][0],
                origin_y + edge_midpoints["right"][1]
            )
            segments.append((point_1, point_2))

        if case == 5 or case == 10:
            point_1 = (
                origin_x + edge_midpoints["top"][0],
                origin_y + edge_midpoints["top"][1]
            )
            point_2 = (
                origin_x + edge_midpoints["bottom"][0],
                origin_y + edge_midpoints["bottom"][1]
            )
            segments.append((point_1, point_2))

        # ambiguos cases
        if case == 6 or case == 9:
            point_1 = (
                origin_x + edge_midpoints["top"][0],
                origin_y + edge_midpoints["top"][1]
            )
            point_2 = (
                origin_x + edge_midpoints["right"][0],
                origin_y + edge_midpoints["right"][1]
            )
            point_3 = (
                origin_x + edge_midpoints["left"][0],
                origin_y + edge_midpoints["left"][1]
            )
            point_4 = (
                origin_x + edge_midpoints["bottom"][0],
                origin_y + edge_midpoints["bottom"][1]
            )

            segments.append((point_1, point_2))
            segments.append((point_3, point_4))

        if case == 7 or case == 8:
            point_1 = (
                origin_x + edge_midpoints["left"][0],
                origin_y + edge_midpoints["left"][1]
            )
            point_2 = (
                origin_x + edge_midpoints["top"][0],
                origin_y + edge_midpoints["top"][1]
            )
            segments.append((point_1, point_2))

    return segments


# function to draw text on an image with a black background for better visibility
# also simplifies the process of drawing text because I am always using th e same font, scale, and thickness
def draw_text_on_image(image, text, position, color=(255, 255, 255)):

    font = cv2.FONT_HERSHEY_PLAIN
    font_thickness = 1
    font_scale = 1

    # get the size of the text to be drawn: width, height, distance from bottom of text to baseline
    (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, font_thickness)

    # draw a filled rectangle behind the text
    cv2.rectangle(image, (position[0], position[1] - text_height - baseline), (position[0] + text_width, position[1] + baseline), (0, 0, 0), cv2.FILLED)

    cv2.putText(image, text, position, cv2.FONT_HERSHEY_PLAIN, font_scale, color, font_thickness)

# hacky, but because my thresholding and marching squares functions are so slow, this sets the region trakcbar to 0 when slice trackbar is changed
# this way user can scroll slices fast, and then change the region of interest after they have found the slice they want to view
def update_slice(val):
    cv2.setTrackbarPos("Region", WINDOW_NAME, 0)
    update_display(val)

# even though i dont use val, i need it because opencv expects a function with a single argument in it's callback function
def update_display(val=None):
    global current_display_image
    global region_of_interest

    # another hacky solution; update_display is called upon created of downsample trakcbar, before slice trackbar is created. This catches the resultant exception.
    try:
        slice_index = cv2.getTrackbarPos("Slice", WINDOW_NAME)
    except:
        slice_index = round(len(dicoms)/2.0)

    region_of_interest = cv2.getTrackbarPos("Region", WINDOW_NAME)

    # ensure even number for better scaling
    try:
        downsample = 2 * cv2.getTrackbarPos("Downsample", WINDOW_NAME)
    except:
        downsample = 2

    # prevent div by 0 error in resize function
    downsample = 1 if downsample == 0 else downsample

    tint_amt = cv2.getTrackbarPos("Tint", WINDOW_NAME)
    tint_amt = tint_amt/100

    # fetch normalized image for display and convert to BGR from monochrome.
    display_image = dicoms[slice_index][0].copy()
    display_image = cv2.cvtColor(display_image, cv2.COLOR_GRAY2BGR)

    if region_of_interest != 0:
        # get the pixel data for the current slice
        data = dicoms[slice_index][1]

        # apply a Gaussian blur to reduce noise
        # kernel is based on inverse of downsample; less downsampling means heavier blur required to smooth data
        kernel = np.floor(1/downsample * 16)
        # ensure odd
        kernel = int(kernel + 1 if kernel % 2 == 0 else kernel)

        data = cv2.GaussianBlur(data, (kernel, kernel), 0)

        #threshold the data to create a binary image of type uint8 for the selected region of interest
        binary_data = threshold_data(data, region_of_interest)

        half_size_binary = cv2.resize(
            binary_data,
            None,
            fx=1/downsample,
            fy=1/downsample,
            interpolation=cv2.INTER_NEAREST
        )

        # colored edge image on black bg
        edges = march_squares(half_size_binary, display_image, downsample)

        # tint region by creating a copy of image and blending between it and single-color layer
        color_layer = np.full_like(display_image, REGION_COLOR)
        region_tint = cv2.addWeighted(display_image, 1-tint_amt, color_layer, tint_amt, 0)

        # copy display image pixels where region mask is not white else write (0,0,0)
        masked_display_image = cv2.bitwise_and(display_image, display_image, mask=cv2.bitwise_not(binary_data))

        # copy tinted pixels where region is white else write (0,0,0)
        region_tint = cv2.bitwise_and(region_tint, region_tint, mask=binary_data)

        # merge tinted region with display image
        display_image = cv2.add(masked_display_image, region_tint)

        # create mask from edges
        edges_mask = cv2.cvtColor(edges, cv2.COLOR_BGR2GRAY)
        # i can use the more efficient openCV threshold function here because my image is uint8 (0-255)
        edges_mask = cv2.threshold(edges_mask, 1, 255, cv2.THRESH_BINARY)[1]

        # copy image pixels where edges mask is not white else write (0,0,0)
        # in service of adding edges atop image
        masked_display_image = cv2.bitwise_and(display_image, display_image, mask=cv2.bitwise_not(edges_mask))
        display_image = cv2.add(masked_display_image, edges)

    # get the size of the display image for positioning text
    display_size = (display_image.shape[1], display_image.shape[0])

    slice_text = f"Slice: {slice_index + 1}/{len(dicoms)-1}\nPosition: {dicoms[slice_index][2]:.2f}mm"
    patient_text = f"Patient ID: {dicoms[slice_index][3]}"
    region_text = f"Region: {anatomy[region_of_interest][0]}"

    draw_text_on_image(display_image, slice_text, (10, 20), color=(255, 255, 255))
    draw_text_on_image(display_image, region_text, (10, 60), color=REGION_COLOR)

    draw_text_on_image(display_image, patient_text, (10, display_size[1] - 10), color=(255, 128, 10))

    current_display_image = display_image.copy()
    cv2.imshow(WINDOW_NAME, display_image)

def main():

    # this ahs to be global so that the update_display function can access it
    global dicoms


    print(f"{Colors.PURPLE}Welcome to the DICOM Viewer!{Colors.ENDC}")

    # identify all dicom series in the master folder
    dicom_series_paths = list_folders(master_folder_path)

    print(f"\n{Colors.PURPLE}{len(dicom_series_paths)} dicom series are available to view: {Colors.ENDC}")

    for item in range(len(dicom_series_paths)):
        print(f"{Colors.BLUE}    ({item + 1}) {dicom_series_paths[item][0]}{Colors.ENDC}")

    print(f"\n{Colors.PURPLE}Enter the number of the dicom series you want to view: {Colors.ENDC}")

    while(True):
        try:
            series_number = input()

            series_number = validate_user_selected_series(series_number, dicom_series_paths)
    
            break
            
        except ValueError as e:
            print(f"{Colors.RED}Error: {e}{Colors.ENDC}")

    series = dicom_series_paths[series_number - 1]

    print(f"\n{Colors.GREEN}You selected: {series[0]}{Colors.ENDC}")

    dicoms = process_dicom_files(collate_dicom_files(series[1]))

    print(f"\n{Colors.PURPLE}Found {len(dicoms)-1} dicom images in the selected series. Proceed? (y/n){Colors.ENDC}")

    while(True):
        try: 
            user_choice = validate_user_yes_or_no(input())

            if user_choice == "y":
                break

            elif user_choice == "n":
                print(f"{Colors.RED}Exiting program...{Colors.ENDC}")
                exit()

        except ValueError as e:
                print(f"{Colors.RED}Error: {e}{Colors.ENDC}")

    print(f"\n{Colors.GREEN}Opened: {series[0]}{Colors.ENDC}")
    print(f"{Colors.BLUE}   press <esc> to close{Colors.ENDC}")
    print(f"{Colors.BLUE}   press <space> to save image{Colors.ENDC}")
    


    # build openCV window
    cv2.namedWindow(WINDOW_NAME)

    # create trackbars for slice selection and region selection
    cv2.createTrackbar(
        "Region",
        WINDOW_NAME,
        0,
        len(anatomy) - 1,
        update_display
    )

    cv2.createTrackbar(
        "Tint",
        WINDOW_NAME,
        25,
        100,
        update_display
    )

    cv2.createTrackbar(
        "Downsample",
        WINDOW_NAME,
        1,
        5,
        update_display
    )

    cv2.createTrackbar(
        "Slice",
        WINDOW_NAME,
        round(len(dicoms)/2.0),
        len(dicoms) - 1,
        update_slice
    )

    # wait for keypress
    while True:
        # 0xFf == binary masks value to keep only lower 8 bits, ensures standard ASCII code
        key = cv2.waitKey(1) & 0xFF

        # esc
        if key == 27:
            break

        # space
        elif key == 32:

            # always update display, catches saving image before sliders changed
            update_display()

            slice_index = cv2.getTrackbarPos("Slice", WINDOW_NAME)

            # create outpur folder for series, do nothing if folder already exists
            output_root = Path("./renders")
            output_folder = output_root / f"images-{series[0]}"
            output_folder.mkdir(parents=True, exist_ok=True)

            # <index>_roi-<region_of_interest>.png
            filename = f"{slice_index + 1}_roi-{anatomy[region_of_interest][0].lower()}.png"

            write_path = output_folder / filename
            cv2.imwrite(write_path, current_display_image)

            print(f"{Colors.GREEN}Saved: {filename}{Colors.ENDC}")

    # pure convenience - optinally wipes render folder
    print(f"{Colors.PURPLE}Clear renders? (y/n){Colors.ENDC}")

    while(True):
        try: 
            user_choice = validate_user_yes_or_no(input())

            if user_choice == "n":
                break

            elif user_choice == "y":
                print(f"{Colors.BLUE}Clearing Renders...{Colors.ENDC}")
                shutil.rmtree(output_root)
                print(f"{Colors.BLUE}Cleared{Colors.ENDC}")
                break

        except ValueError as e:
                print(f"{Colors.RED}Error: {e}{Colors.ENDC}")

    print(f"\n{Colors.RED}Quitting.{Colors.ENDC}")

if __name__ == "__main__":
    main()