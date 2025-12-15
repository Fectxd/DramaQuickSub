"""
重新生成符合PyInstaller要求的ico文件
"""
from PIL import Image
import os

# 检查是否有icon.svg
if os.path.exists('icon.svg'):
    try:
        from cairosvg import svg2png
        import io
        
        # 从SVG生成多尺寸PNG
        sizes = [256, 128, 64, 48, 32, 16]
        images = []
        
        print("正在从SVG生成ICO...")
        for size in sizes:
            png_data = svg2png(url='icon.svg', output_width=size, output_height=size)
            img = Image.open(io.BytesIO(png_data))
            images.append(img)
            print(f"  生成 {size}x{size} 图标")
        
        # 保存为ICO（确保格式正确）
        images[0].save('icon_new.ico', format='ICO', 
                      sizes=[(s, s) for s in sizes], 
                      append_images=images[1:])
        
        # 备份旧文件并替换
        if os.path.exists('icon.ico'):
            os.rename('icon.ico', 'icon_old.ico')
            print("  旧图标已备份为 icon_old.ico")
        
        os.rename('icon_new.ico', 'icon.ico')
        print("✓ icon.ico 重新生成成功！")
        print(f"  文件大小: {os.path.getsize('icon.ico')} 字节")
        
    except ImportError:
        print("缺少依赖，请运行: pip install cairosvg pillow")
else:
    # 如果没有SVG，尝试优化现有的ICO
    if os.path.exists('icon.ico'):
        print("正在优化现有的ICO文件...")
        try:
            img = Image.open('icon.ico')
            
            # 重新保存，确保格式正确
            sizes = [256, 128, 64, 48, 32, 16]
            images = []
            
            for size in sizes:
                resized = img.resize((size, size), Image.Resampling.LANCZOS)
                images.append(resized)
                print(f"  生成 {size}x{size} 图标")
            
            # 备份并保存
            os.rename('icon.ico', 'icon_old.ico')
            images[0].save('icon.ico', format='ICO', 
                          sizes=[(s, s) for s in sizes], 
                          append_images=images[1:])
            
            print("✓ icon.ico 优化成功！")
            print(f"  文件大小: {os.path.getsize('icon.ico')} 字节")
            
        except Exception as e:
            print(f"✗ 优化失败: {e}")
    else:
        print("✗ 未找到 icon.svg 或 icon.ico")
