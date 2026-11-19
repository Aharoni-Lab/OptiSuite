"""Run the OmniTargetReader YOLO pipeline on one image (fresh process). Prints JSON."""
import json, os, sys, time
os.environ.setdefault("YOLO_OFFLINE", "1")
omni = sys.argv[1]; img = os.path.abspath(sys.argv[2])
os.chdir(omni); sys.path.insert(0, omni)
import usaf_algo as ua
out = {"method": "yolo", "image": img}
t = time.time()
for flip in (True, False):          # their default is flipped; retry unflipped if it fails
    ua.FLIPED_TARGET = flip
    ua.valid_squares.clear()
    try:
        r = ua.find_usaf_score(img, ua.MODEL_PATH)
        if r:
            out.update(result=[int(r[0]), int(r[1])], flipped=flip); break
        out["error"] = "no result"
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
out["seconds"] = round(time.time() - t, 1)
print("@@" + json.dumps(out))
