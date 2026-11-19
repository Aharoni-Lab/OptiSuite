"""Run the usaf_target (SIFT registration + YOLO classifier) pipeline on one image. Prints JSON."""
import json, os, sys, time, tempfile
os.environ.setdefault("YOLO_OFFLINE", "1")
pkg_parent = sys.argv[1]; img = os.path.abspath(sys.argv[2]); mode = sys.argv[3] if len(sys.argv) > 3 else "auto"
work = tempfile.mkdtemp(); os.chdir(work)        # pattern_crop dir is cwd-relative
sys.path.insert(0, pkg_parent)
import matplotlib; matplotlib.use("Agg")
from usaf_registration import UsafRegistration
u = UsafRegistration()
u.C.PT_TRANSFORM = mode
u.C.USE_SIFT_REF_CALIBRATION = mode in ("classic with sift", "sift", "elastix", "auto")
out = {"method": f"sift:{mode}", "image": img}
t = time.time()
try:
    r = u.score_image_routine(img)
    if r:
        out["result"] = [int(r[0][0]), int(r[0][1])]
    else:
        out["error"] = "no result"
except Exception as e:
    out["error"] = f"{type(e).__name__}: {e}"
out["seconds"] = round(time.time() - t, 1)
print("@@" + json.dumps(out))
