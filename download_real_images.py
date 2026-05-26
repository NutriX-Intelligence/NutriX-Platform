import os
import requests

def download_image(url: str, dest_path: str):
    print(f"Downloading {url} -> {dest_path}...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        with open(dest_path, "wb") as f:
            f.write(response.content)
        print("Success!")
    except Exception as e:
        print(f"Failed to download: {e}")

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    test_img_dir = os.path.join(base_dir, "dataset", "test_images")
    os.makedirs(test_img_dir, exist_ok=True)

    # Dictionary of food name to high-quality Unsplash image URLs
    # Using smaller size parameters (w=640) to download quickly
    urls = {
        "apple.jpg": "https://images.unsplash.com/photo-1560806887-1e4cd0b6cbd6?w=640&q=80",
        "banana.jpg": "https://images.unsplash.com/photo-1571771894821-ce9b6c11b08e?w=640&q=80",
        "roti.jpg": "https://images.unsplash.com/photo-1627834377411-8da5f4f09de8?w=640&q=80",
        "bread.jpg": "https://images.unsplash.com/photo-1509440159596-0249088772ff?w=640&q=80",
        "cucumber.jpg": "https://images.unsplash.com/photo-1604908176997-125f25cc6f3d?w=640&q=80",
        "tomato.jpg": "https://images.unsplash.com/photo-1595855759920-86582396756a?w=640&q=80",
        "raw_mango.jpg": "https://images.unsplash.com/photo-1553279768-865429fa0078?w=640&q=80",
        "paneer_tikka.jpg": "https://images.unsplash.com/photo-1567188040759-fb8a883dc6d8?w=640&q=80"
    }

    for name, url in urls.items():
        dest = os.path.join(test_img_dir, name)
        download_image(url, dest)

if __name__ == "__main__":
    main()
