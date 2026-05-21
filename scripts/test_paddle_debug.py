"""Debug script to inspect PaddleOCR 3.5 output structure."""
import os, sys, json

os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] = "0"

from paddleocr import PaddleOCR

# Use the test image in the repo root
img_path = os.path.join(os.path.dirname(__file__), "..", "f475c16a-1fa2-408b-b3ab-7f1eaa267a7a.jpg")
if not os.path.exists(img_path):
    print("ERROR: test image not found at", img_path)
    sys.exit(1)

print(f"Image: {img_path}")
print("=" * 60)

reader = PaddleOCR(
    lang="en",
    enable_mkldnn=False,
    return_word_box=True,
    use_doc_orientation_classify=True,
    use_doc_unwarping=True,
)

print("\n--- Calling reader.predict() ---")
raw = reader.predict(img_path)

print(f"\nraw type: {type(raw).__name__}")
print(f"is generator: {hasattr(raw, '__next__')}")

result_list = list(raw)
print(f"result_list length: {len(result_list)}")

for idx, item in enumerate(result_list[:3]):
    print(f"\n--- Item {idx} ---")
    print(f"  type: {type(item).__name__}")

    # Check dict-like access
    if hasattr(item, "keys"):
        keys = list(item.keys())
        print(f"  keys: {keys}")
        for key in keys:
            val = item[key]
            vtype = type(val).__name__
            if isinstance(val, (list, tuple)):
                print(f"  {key} ({vtype}): len={len(val)}, first_item_type={type(val[0]).__name__ if val else 'empty'}")
                if val and key in ("rec_texts", "rec_scores"):
                    print(f"    sample: {val[:5]}")
                if val and key == "dt_polys":
                    print(f"    sample[0]: {val[0]}")
                if val and key == "text_word":
                    print(f"    sample[0]: {val[0]}")
                if val and key == "text_word_boxes":
                    print(f"    sample[0] type: {type(val[0]).__name__}, len={len(val[0]) if hasattr(val[0], '__len__') else 'N/A'}")
            elif isinstance(val, str):
                print(f"  {key} ({vtype}): {val[:100]}")
            elif isinstance(val, (int, float)):
                print(f"  {key} ({vtype}): {val}")
            else:
                print(f"  {key} ({vtype}): {repr(val)[:100]}")
    
    # Check attribute-like access
    for attr in ("rec_texts", "rec_scores", "dt_polys", "text_word", "text_word_boxes"):
        if hasattr(item, attr):
            val = getattr(item, attr)
            if val is not None:
                print(f"  attr.{attr}: type={type(val).__name__}, len={len(val) if hasattr(val, '__len__') else 'N/A'}")
    
    # Check if it's a list (legacy format)
    if isinstance(item, (list, tuple)):
        print(f"  (list/tuple) length: {len(item)}")
        if item:
            print(f"  first element type: {type(item[0]).__name__}")

    # dir() for unknown types
    if not hasattr(item, "keys") and not isinstance(item, (list, tuple)):
        interesting = [a for a in dir(item) if not a.startswith("_")]
        print(f"  dir() (non-underscore): {interesting[:20]}")

print("\n--- Done ---")
