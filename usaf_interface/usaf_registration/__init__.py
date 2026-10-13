from .constants import UsafConfig



class UsafRegistration:
    """USAF registration entry point; owns a per-instance UsafConfig."""

    def __init__(self, config: UsafConfig | None = None):
        self.C = config if config is not None else UsafConfig()
    
    from .classic_warp import make_dummy_valid_square
    from .classic_warp import is_valid_square
    from .classic_warp import find_square_corners
    from .classic_warp import bright_pixels_as_corners
    from .classic_warp import find_white_corner_in_region
    from .classic_warp import find_target_orientation
    from .classic_warp import get_adjusted_top_corners_from_enclosing_rectangle

    from .elastix_warp import normalize_for_registration
    from .elastix_warp import _run_transformix_batch
    from .elastix_warp import fast_transformix_point
    from .elastix_warp import transformix_point
    from .elastix_warp import ref_usaf_point_to_target
    from .elastix_warp import fast_ref_usaf_point_to_target
    from .elastix_warp import show_itkelastix_preview
    from .elastix_warp import setup_itkelastix_ref_mapping

    from .helper import sample_line_profile
    from .helper import is_image_clear
    from .helper import normalize_image_contrast
    from .helper import gradient_visualization
    from .helper import usaf_lp_per_mm
    from .helper import usaf_resolution_mm

    from .pattern_crop import scanline_region_cropping
    from .pattern_crop import classify_pattern_resolution
    from .pattern_crop import find_pattern_crop
    from .pattern_crop import show_pattern_classification_results
    from .pattern_crop import augumented_single_scanline_detection
    from .pattern_crop import verify_pattern_crops

    from .pt_adjust import find_replacement_keypoints
    from .pt_adjust import apply_point_adjustment_algorithm
    from .pt_adjust import extend_line

    from .scoring import score_pattern_crops
    from .scoring import find_best_focus_group

    from .sift_warp import get_sift_reference_image
    from .sift_warp import _sift_ref_origin_for_target
    from .sift_warp import sift_homography_with_origin

    from .transforms import get_rotated_pt
    from .transforms import usaf2screen_classic
    from .transforms import usaf2ref
    from .transforms import usaf2screen_homography
    from .transforms import fast_usaf2screen_homography
    from .transforms import ref_to_screen_homography_matrix
    from .transforms import yolo2screen

    from .usaf_algo import map_ref_corners_classic
    from .usaf_algo import map_ref_corners_sift
    from .usaf_algo import grid_calculation
    from .usaf_algo import coordinate_calibration
    from .usaf_algo import usaf_point_to_screen
    from .usaf_algo import scanline_visualization
    from .usaf_algo import calculate_scanline_contrast_scores
    from .usaf_algo import find_usaf_score
    from .usaf_algo import find_dominant_angle_window_center
    from .usaf_algo import angle_to_dominant_bucket_index
    from .usaf_algo import bucketize_angles_around_dominant
    from .usaf_algo import auto_configurator
    from .usaf_algo import clean_up
    from .usaf_algo import load_config
    
    # main function
    from .usaf_algo import score_image_routine

    from .yolo_model import classify_resolution
    from .yolo_model import count_4pts_pattern
    from .yolo_model import yolo_4pt_calculation
    from .yolo_model import get_yolo_model
    from .yolo_model import extract_yolo_detections
    from .yolo_model import visualize_detections
    from .yolo_model import detect_single_scanline_keypoints

    from .yolo_model import BASE_DIR
    from .yolo_model import MODEL_PATH
    from .yolo_model import NUM_MODEL_PATH
    from .yolo_model import RES_MODEL_PATH
    from .yolo_model import PT4_MODEL_PATH
    from .yolo_model import SINGLE_SCANLINE_MODEL_PATH



__all__ = ["UsafRegistration"]