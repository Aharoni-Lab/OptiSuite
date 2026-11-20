from .constants import UsafConfig



class UsafRegistration:
    """USAF registration entry point; owns a per-instance UsafConfig."""

    def __init__(self, config: UsafConfig | None = None):
        self.C = config if config is not None else UsafConfig()

    from .classic_warp import make_dummy_valid_square
    from .classic_warp import is_valid_square
    from .classic_warp import find_square_corners

    from .helper import sample_line_profile
    from .helper import extend_line
    from .helper import normalize_image_contrast
    from .helper import usaf_lp_per_mm
    from .helper import usaf_resolution_mm

    from .nested_match import nested_scanline_contrast_scores
    from .nested_match import nested_match_layers
    from .nested_match import read_start_group
    from .usaf_algo import calculate_scanline_contrast_scores
    from .usaf_algo import bundle_scanline_scores
    from .usaf_algo import find_usaf_score
    from .usaf_algo import score_image_routine

    from .yolo_model import count_4pts_pattern
    from .yolo_model import yolo_4pt_calculation
    from .yolo_model import get_yolo_model
    from .yolo_model import extract_yolo_detections
    from .yolo_model import visualize_detections

    from .yolo_model import BASE_DIR
    from .yolo_model import MODEL_PATH
    from .yolo_model import PT4_MODEL_PATH



__all__ = ["UsafRegistration"]
