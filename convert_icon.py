"""
Convert SVG icon to ICO format for Windows executable
"""
try:
    from cairosvg import svg2png
    from PIL import Image
    import io
    
    # Convert SVG to PNG at multiple sizes
    sizes = [256, 128, 64, 48, 32, 16]
    images = []
    
    for size in sizes:
        png_data = svg2png(url='icon.svg', output_width=size, output_height=size)
        img = Image.open(io.BytesIO(png_data))
        images.append(img)
    
    # Save as ICO
    images[0].save('icon.ico', format='ICO', sizes=[(s, s) for s in sizes], append_images=images[1:])
    print("✓ icon.ico created successfully!")
    
except ImportError as e:
    print(f"Please install required packages: pip install cairosvg pillow")
    print(f"Error: {e}")
