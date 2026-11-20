from pathlib import Path


class UsafConfig:
    """Per-instance USAF registration settings and runtime state."""

    def __init__(self):
        # main settings
        self.DEBUG_MODE = False              # debug log + plots
        self.PREVIEW_MODE = False            # show the scored scanlines
        self.FLIPED_TARGET = True            # true if target is mirrored; set per image from the YOLO keypoints
        self.SCORE_THRESHOLD = 0.2           # scanline contrast needed (with >= 2 local minima) to call a glyph resolved
        self.SCORE_METHOD = "min"            # "mean", "min", "max", "raw": merge of the vertical and horizontal scores

        # nested matching (nested_match.py): glyph boxes carried from the annotated templates by SIFT,
        # one nested level at a time, each found inside the level above
        self.NESTED_MATCH = "own_template"
        # "own_template": each nested level matched with its own template
        # "parent_crop": each nested level matched with its region of the template one level up
        self.NESTED_GROUP = None             # biggest group in view; None -> read the printed group numbers, else 8 - 2*pattern_count
        self.NESTED_MAX_GROUP = 7            # groups past this are matched but not scored (groups 8-9 later)

        self.BASE_DIR = str(Path(__file__).resolve().parent)
        self.LOG_PATH = Path(self.BASE_DIR).parent.parent / "logs"
        self.LOG_PATH.mkdir(parents=True, exist_ok=True)

        # runtime state (per image)
        self.valid_squares = []              # detected white squares, largest first (classic_warp.find_square_corners)
        self.pattern_count = 0               # YOLO 4-point pattern count = nested levels in view
        self.current_image_path = None
        self.current_raw_image = None        # image before contrast normalization (scanline checker input)
        self.nested_result = None            # record of the nested matching (start group, layers, checker)
        self.score_table = {}                # scan index -> [group, element], set by the nested matching
        self._MODEL_CACHE = {}
