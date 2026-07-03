from pathlib import Path


# main settings
DEBUG_MODE = False              # debug log + photo
PREVIEW_MODE = False            # overview photo
FLIPED_TARGET = False            # true if target is fliped
G1 = 2                          # first group number
PT_TRANSFORM = "classic with sift"        
# "classic with sift", "classic", "sift", "elastix", method to transform the reference 
# target-space point to test image for scoring and adjustment


# gradient settings
GRADIENT_MIN = False
GRADIENT_PLOT_ENABLE = False       # visualize selected scanline intensity + gradient
GRADIENT_PLOT_GROUP = 3            # group to inspect when GRADIENT_PLOT_ENABLE is True
GRADIENT_PLOT_ELEMENT = 4          # element to inspect when GRADIENT_PLOT_ENABLE is True
GRADIENT_PLOT_ORIENTATION = "both" # "vertical"->scanline, "horizontal"->scanline, "both"->scanline


# YOLO settings
YOLO_DETECT = False              # yolo detect scanline
YOLO_CLASSIFICATION = True      # yolo classify pattern
PATTERN_CLASSIFICATION_SHOW_PLOT = PREVIEW_MODE
PATTERN_CLASSIFICATION_ROWS_PER_PAGE = 6
CROP_DIR = Path("pattern_crop")          # directory to save pattern crops for yolo classification
CONST_LABEL = True                       # use constant label for yolo classification crop img


# legacy algorithm settings
SUBPIXEL = True                 # subpixel refinement for corner detection best for large target
RETRY_OUTER = False              # if only inner corner detected, expand the scanline to outer target
RETRY_OFF_IMAGE = False         # if any scanline goes out of image, retry with next best square
AUTO_ADJUST = False             # shorten the scanline until the color on the two point are white (above ADJUST_THRESH)
ADJUST_THRESH = 0.8             # white threshold, between 0 and 1 of the normalzed grayscale value
FOUR_KP = False                  # use four reference corners to calibrate the target
CORNER_METHOD = "threshold"     # "threshold", "default", method to detect the corner
SCORE_METHOD = "max"           # "mean", "min", "max", "raw", method to merge the score from horizational and vertical scanlines
CROPED_WINDOW_RETRY = False     # if the corner detection window is off image, retry with next best square
FOCUS_GROUP_LAST_ABOVE_THRESHOLD = False  # True: last score above threshold in loop; False: inflection


# SIFT calibration settings
# if True, use SIFT+homography for secondary ref corners
SIFT_CONFIG_LIST = [
    {
        "REF_IMAGE_PATH" : "test_img/image_g67only.png",
        "REF_ORIGIN" : (425.0, 170.0),
        "REF_PIXELS_PER_UNIT_X" : 91.0,
        "REF_PIXELS_PER_UNIT_Y" : 91.0,
        "ANGLE" : -0.60,
    },
    {
        "REF_IMAGE_PATH" : "test_img/SIFT_ref_image.png",
        "REF_ORIGIN" : (195.0, 66.5),
        "REF_PIXELS_PER_UNIT_X" : 44.3,
        "REF_PIXELS_PER_UNIT_Y" : 43.0,
        "ANGLE" : 0.0,
    },
    {
        # "REF_IMAGE_PATH" : "test_img/new_SIFT_ref_image_bordered.png",
        # "REF_ORIGIN" : (1013.0, 343.5),
        # "REF_PIXELS_PER_UNIT_X" : 226.1,
        # "REF_PIXELS_PER_UNIT_Y" : 223.0,
        # "ANGLE" : -0.235,
        "REF_IMAGE_PATH" : "test_img/SIFT_ref_image.png",
        "REF_ORIGIN" : (195.0, 66.5),
        "REF_PIXELS_PER_UNIT_X" : 44.3,
        "REF_PIXELS_PER_UNIT_Y" : 43.0,
        "ANGLE" : 0.0,
    },
]
USE_SIFT_REF_CALIBRATION = True if PT_TRANSFORM == "classic with sift" or PT_TRANSFORM == "sift" or PT_TRANSFORM == "elastix" else False 
SIFT_REF_IMAGE_PATH = SIFT_CONFIG_LIST[2]["REF_IMAGE_PATH"]
SIFT_REF_ORIGIN = SIFT_CONFIG_LIST[2]["REF_ORIGIN"]  # origin on reference image in pixel coordinates(1010.0, 343.5)
SIFT_REF_PIXELS_PER_UNIT_X = SIFT_CONFIG_LIST[2]["REF_PIXELS_PER_UNIT_X"]  # x-axis pixels per unit on reference image
SIFT_REF_PIXELS_PER_UNIT_Y = SIFT_CONFIG_LIST[2]["REF_PIXELS_PER_UNIT_Y"]  # y-axis pixels per unit on reference image
SIFT_ANGLE = SIFT_CONFIG_LIST[2]["ANGLE"]

SIFT_REF_RATIO_TEST = 0.75
SIFT_REF_RANSAC_REPROJ = 3.0
SIFT_REF_MIN_MATCH_COUNT = 8
SIFT_REF_SHOW_PLOT = DEBUG_MODE


# ITK calibration settings
 # set False to use the original SIFT-only mapping
USE_ITKELASTIX_REF_CALIBRATION = True if PT_TRANSFORM == "elastix" else False 
ITKELASTIX_PARAMETER_MAP = "bspline"  # deformable; use "rigid" to switch back
ITKELASTIX_ROI_MARGIN = 80
ITKELASTIX_FINAL_GRID_SPACING = 10.0  # lower = more local deformation, higher = smoother
ITKELASTIX_NUMBER_OF_RESOLUTIONS = 5
ITKELASTIX_MAX_ITERATIONS = 512
ITKELASTIX_SHOW_PLOT = DEBUG_MODE
ITKELASTIX_LOG_TO_CONSOLE = True






def get_image_paths(folder_path, recursive=False):
    image_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
    folder = Path(folder_path)
    paths = folder.rglob("*") if recursive else folder.iterdir()
    return sorted(str(path) for path in paths if path.is_file() and path.suffix.lower() in image_extensions)

images = [
    'test_img/test_image_new.png',
    'test_img/test_image_g4e4.png',
    'test_img/test_image_g5e4.png',
    'test_img/af_Z59_370_183653_20260227_183653.png',
    'test_img/test_image_g3e6.png',
    'test_img/test_image_g6e6.png',
    'test_img/af_z59_880_cam1_VEN-505-36U3M-M01_20260227_163955.png',
    'test_img/image_g67only.png',
    'test_img/image.png',
    'test_img/Image0001.bmp',
    'test_img/Screenshot_2026-05-06_085659.png',
]


# Process images
# images = get_image_paths("training_img\\not_fliped")
# print(f"Found {len(list(images))} files in folder:")
# for path in images:
#     print(str(path))
# print("---------------------------------")







# Global variables
valid_squares = []
retry_count = 0
pattern_count = 0
current_image_label = "image"
_sift_ref_image_cache = None
_sift_h_matrix = None  # ref->test homography from last coordinate_calibration (SIFT path)
_itk_transform_params = None  # optional refinement from SIFT-warped reference target-space -> target
_itk_moving_image = None
_itk_output_dir = None
_itk_roi_offset = (0, 0)
_itk_point_cache = {}
initial_angle = 0



#anchor coordinate for performing secondary coordinate calibration
top_left_ref_coord = (2.64, 0.5)
top_right_ref_coord = (-3.64, 0.5)
low_left_ref_coord = (2.39,-5.89)
low_right_ref_coord = (-3.57,-5.88)


# scanline definition in usaf coordinate
# Define points as (local_x, local_y) relative to the center of the square, in units of side_length
# Every two points (0&1, 2&3, etc.) will form one line segment for scoring
g2_x = -3.2
g3_x = 2.5
g4_x = -0.56
g5_x = 0.87
g6_x = 0.112

g6y_scale = 1.027
g5y_scale = 1.023
g4y_scale = 1.026
g3y_scale = 1.03
g2y_scale = 1.03

g6x_scale = 0.922
g5x_scale = 1.00
g4x_scale = 1.13
g3x_scale = 1.015
g2x_scale = 1.06

g7x_offset = -0.01
g7y_offset = -0.08
g7y_scale = 1.019

group_positions = {
    
    0: (g2_x, 0.35),            1: (g2_x, -0.37),
    2: (g2_x, -1.31),           3: (g2_x, -1.96),
    4: (g2_x, -2.8),            5: (g2_x, -3.40),
    
    6: (g3_x, 0.43),            7: (g3_x, 0.01),
    8: (g3_x, -0.5),            9: (g3_x, -0.88),
    10: (g3_x, -1.37),          11: (g3_x, -1.70),
    12: (g3_x, -2.08-0.05),     13: (g3_x, -2.38-0.05),
    14: (g3_x, -2.73-0.05),     15: (g3_x, -3.01-0.05),
    16: (g3_x, -3.32-0.07),     17: (g3_x, -3.57-0.07),
    
    18: (0.79, -3.15-0.057),    19: (0.79, -3.37-0.057),
    20: (g4_x, -1.84-0.03),     21: (g4_x, -2.04-0.03),
    22: (g4_x, -2.26-0.05),     23: (g4_x, -2.44-0.05),
    24: (g4_x, -2.63-0.05),     25: (g4_x, -2.79-0.05),
    26: (g4_x, -2.97-0.05),     27: (g4_x, -3.1-0.05),
    28: (g4_x, -3.26-0.05),     29: (g4_x, -3.39-0.05),

    30: (g5_x, -1.838-0.03),    31: (g5_x, -1.944-0.03),
    32: (g5_x, -2.072-0.038),   33: (g5_x, -2.168-0.038),
    34: (g5_x, -2.277-0.04),    35: (g5_x, -2.365-0.04),
    36: (g5_x, -2.468-0.037),   37: (g5_x, -2.538-0.044),
    38: (g5_x, -2.64-0.04),     39: (g5_x, -2.696-0.04),
    40: (g5_x, -2.782-0.045),   41: (g5_x, -2.836-0.045),
    
    42: (0.44, -2.78-0.01),     43: (0.44, -2.82-0.01),
    44: (g6_x, -2.453),         45: (g6_x, -2.49),
    46: (g6_x, -2.557),         47: (g6_x, -2.59),
    48: (g6_x, -2.654),         49: (g6_x, -2.681),
    50: (g6_x-0.003, -2.735),   51: (g6_x-0.003, -2.755),
    52: (g6_x-0.005, -2.812),    53: (g6_x-0.005, -2.83),

    54: (0.3997 + g7x_offset, (-2.3382 + g7y_offset) * g7y_scale),                            55: (0.4274 + g7x_offset, (-2.3384 + g7y_offset) * g7y_scale),
    56: (0.4097 + g7x_offset, (-2.3914 + g7y_offset) * g7y_scale),                            57: (0.4337 + g7x_offset, (-2.3912 + g7y_offset) * g7y_scale),
    58: (0.4158 + g7x_offset, (-2.4394 + g7y_offset) * g7y_scale),                            59: (0.438 + g7x_offset, (-2.4398 + g7y_offset) * g7y_scale),
    60: (0.4226 + g7x_offset, (-2.4828 + g7y_offset) * g7y_scale),                            61: (0.443 + g7x_offset, (-2.4832 + g7y_offset) * g7y_scale),
    62: (0.4294 + g7x_offset, (-2.522 + g7y_offset) * g7y_scale),                             63: (0.4462 + g7x_offset, (-2.5223 + g7y_offset) * g7y_scale),
    64: (0.4352 + g7x_offset, (-2.557 + g7y_offset) * g7y_scale),                             65: (0.4493 + g7x_offset, (-2.557 + g7y_offset) * g7y_scale),







    66: (-2.05 * g2x_scale, -0.003 * g2y_scale),      67: (-1.26 * g2x_scale, 0.005 * g2y_scale),
    68: (-2.19 * g2x_scale, -1.625 * g2y_scale),     69: (-1.51 * g2x_scale, -1.617 * g2y_scale),
    70: (-2.33 * g2x_scale, -3.04 * g2y_scale),      71: (-1.71 * g2x_scale, -3.046 * g2y_scale),

    72: (1.3 * g3x_scale, 0.2 * g3y_scale),          73: (1.75 * g3x_scale, 0.2 * g3y_scale),
    74: (1.435 * g3x_scale, -0.707 * g3y_scale),     75: (1.835 * g3x_scale, -0.707 * g3y_scale),
    76: (1.563 * g3x_scale, -1.498 * g3y_scale),     77: (1.92 * g3x_scale, -1.496 * g3y_scale),
    78: (1.68 * g3x_scale, -2.218 * g3y_scale),      79: (1.99 * g3x_scale, -2.213 * g3y_scale),
    80: (1.775 * g3x_scale, -2.85 * g3y_scale),      81: (2.062 * g3x_scale, -2.85 * g3y_scale),
    82: (1.867 * g3x_scale, -3.42 * g3y_scale),      83: (2.118 * g3x_scale, -3.422 * g3y_scale),

    84: (0.218 * g4x_scale, -3.234 * g4y_scale),     85: (0.444 * g4x_scale, -3.227 * g4y_scale),
    86: (-0.258 * g4x_scale, -1.929 * g4y_scale),    87: (-0.056 * g4x_scale, -1.931 * g4y_scale),
    88: (-0.289 * g4x_scale, -2.331 * g4y_scale),    89: (-0.112 * g4x_scale, -2.333 * g4y_scale),
    90: (-0.329 * g4x_scale, -2.692 * g4y_scale),    91: (-0.16 * g4x_scale, -2.691 * g4y_scale),
    92: (-0.351 * g4x_scale, -3.007 * g4y_scale),    93: (-0.211 * g4x_scale, -3.005 * g4y_scale),
    94: (-0.38 * g4x_scale, -3.29 * g4y_scale),      95: (-0.253 * g4x_scale, -3.289 * g4y_scale),

    96: (0.583 * g5x_scale, -1.8684 * g5y_scale),    97: (0.7 * g5x_scale, -1.87 * g5y_scale),
    98: (0.6256 * g5x_scale, -2.0996 * g5y_scale),   99: (0.72 * g5x_scale, -2.1 * g5y_scale),
    100: (0.65 * g5x_scale, -2.3 * g5y_scale),       101: (0.74 * g5x_scale, -2.3 * g5y_scale),
    102: (0.68 * g5x_scale, -2.48 * g5y_scale),      103: (0.76 * g5x_scale, -2.48 * g5y_scale),
    104: (0.71 * g5x_scale, -2.64 * g5y_scale),      105: (0.78 * g5x_scale, -2.64 * g5y_scale),
    106: (0.7355 * g5x_scale, -2.7845 * g5y_scale),  107: (0.785 * g5x_scale, -2.786 * g5y_scale),

    108: (0.336 * g6x_scale, -2.731 * g6y_scale),    109: (0.390 * g6x_scale, -2.7295 * g6y_scale),
    110: (0.198 * g6x_scale, -2.4046 * g6y_scale),   111: (0.2464 * g6x_scale, -2.4054 * g6y_scale),
    112: (0.1885 * g6x_scale, -2.506 * g6y_scale),   113: (0.2324 * g6x_scale, -2.507 * g6y_scale),
    114: (0.1796 * g6x_scale, -2.5945 * g6y_scale),  115: (0.2195 * g6x_scale, -2.5933 * g6y_scale),
    116: (0.173 * g6x_scale, -2.6736 * g6y_scale),   117: (0.208 * g6x_scale, -2.6738 * g6y_scale),
    118: (0.166 * g6x_scale, -2.744 * g6y_scale),    119: (0.1975 * g6x_scale, -2.7446 * g6y_scale),

    120: (0.4615 + g7x_offset, (-2.3234 + g7y_offset) * g7y_scale),                           121: (0.461 + g7x_offset, (-2.352 + g7y_offset) * g7y_scale),
    122: (0.4615 + g7x_offset, (-2.3808 + g7y_offset) * g7y_scale),                           123: (0.4618 + g7x_offset, (-2.404 + g7y_offset) * g7y_scale),
    124: (0.4654 + g7x_offset, (-2.4287 + g7y_offset) * g7y_scale),                           125: (0.464 + g7x_offset, (-2.451 + g7y_offset) * g7y_scale),
    126: (0.466 + g7x_offset, (-2.474 + g7y_offset) * g7y_scale),                             127: (0.4662 + g7x_offset, (-2.492 + g7y_offset) * g7y_scale),
    128: (0.468 + g7x_offset, (-2.515 + g7y_offset) * g7y_scale),                             129: (0.467 + g7x_offset, (-2.53 + g7y_offset) * g7y_scale),
    130: (0.47 + g7x_offset, (-2.55 + g7y_offset) * g7y_scale),                               131: (0.4705 + g7x_offset, (-2.5622 + g7y_offset) * g7y_scale),
    
}


#score table to covert score to group and element number
score_table = {}
def initialize_score_table():
    global score_table
    score_table = {
        0: [G1,2],
        1: [G1,3],
        2: [G1,4],
        3: [G1+1,1],
        4: [G1+1,2],
        5: [G1+1,3],
        6: [G1+1,4],
        7: [G1+1,5],
        8: [G1+1,6],
        9: [G1+2,1],
        10: [G1+2,2],
        11: [G1+2,3],
        12: [G1+2,4],
        13: [G1+2,5],
        14: [G1+2,6],
        15: [G1+3,1],
        16: [G1+3,2],
        17: [G1+3,3],
        18: [G1+3,4],
        19: [G1+3,5],
        20: [G1+3,6],
        21: [G1+4,1],
        22: [G1+4,2],
        23: [G1+4,3],
        24: [G1+4,4],
        25: [G1+4,5],
        26: [G1+4,6],
        27: [G1+5,1],
        28: [G1+5,2],
        29: [G1+5,3],
        30: [G1+5,4],
        31: [G1+5,5],
        32: [G1+5,6]
    }
initialize_score_table()


prefer_dir_table =  [
                    [1, 3, 4, 2], 
                    [3, 2, 1, 4],
                    [2, 4, 3, 1],
                    [4, 1, 2, 3] 
                    ]