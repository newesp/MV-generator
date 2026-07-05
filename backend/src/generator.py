import os
import glob

def get_local_images(inputs_dir: str):
    """
    Scans the inputs_dir for images (jpg, png, jpeg).
    Returns a sorted list of absolute file paths.
    """
    extensions = ["*.jpg", "*.jpeg", "*.png"]
    images = []
    for ext in extensions:
        images.extend(glob.glob(os.path.join(inputs_dir, ext)))
        images.extend(glob.glob(os.path.join(inputs_dir, ext.upper())))
    
    return sorted(list(set(images)))

def generate_image_google_api(prompt: str, output_path: str, project_id: str, location: str):
    """
    Generates an image using Google Cloud Vertex AI or Gemini API (Imagen).
    This is a stub for the actual API call.
    For the MVP, we assume the user has set up the google-genai SDK or uses local images if this fails.
    """
    # TODO: Implement actual google-genai or Vertex AI Imagen 3 call
    # from google import genai
    # client = genai.Client()
    # result = client.models.generate_images(...)
    print(f"[Generator] Call Google API to generate image with prompt: {prompt}")
    print("[Generator] Not fully implemented yet. Falling back to local images.")
    return None

def prepare_visual_assets(num_segments: int, inputs_dir: str, preferred_image: str | None = None):
    """
    Returns a list of image paths of length `num_segments`.
    Loops through available local images.
    """
    if preferred_image:
        if not os.path.exists(preferred_image):
            raise ValueError(f"Preferred image not found: {preferred_image}")
        return [preferred_image for _ in range(num_segments)]

    images = get_local_images(inputs_dir)
    if not images:
        raise ValueError(f"No images found in {inputs_dir}. Please upload some images.")
    
    # Loop images if not enough for all segments
    assets = []
    for i in range(num_segments):
        assets.append(images[i % len(images)])
        
    return assets
