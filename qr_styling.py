"""
QR Code Styling System
Handles custom QR code styling, templates, and visual customization
"""

import qrcode
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io
import os
from typing import Dict, Any, List, Optional, Tuple
import json
from logger_config import logger


class QRStyler:
    """Advanced QR code styling and template system"""
    
    def __init__(self):
        self.templates = self._load_default_templates()
        self.fonts = self._load_fonts()
        self.patterns = self._load_patterns()
    
    def apply_style(self, qr_image: Image.Image, style_config: Dict[str, Any]) -> Image.Image:
        """Apply comprehensive styling to QR code"""
        
        try:
            # Convert to RGB if needed
            if qr_image.mode != 'RGB':
                qr_image = qr_image.convert('RGB')
            
            # Apply base styling
            styled_qr = qr_image.copy()
            
            # Apply colors
            if 'colors' in style_config:
                styled_qr = self._apply_colors(styled_qr, style_config['colors'])
            
            # Apply pattern
            if 'pattern' in style_config:
                styled_qr = self._apply_pattern(styled_qr, style_config['pattern'])
            
            # Add frame/border
            if 'frame' in style_config:
                styled_qr = self._add_frame(styled_qr, style_config['frame'])
            
            # Add logo
            if 'logo' in style_config:
                styled_qr = self._add_logo(styled_qr, style_config['logo'])
            
            # Add text overlay
            if 'text_overlay' in style_config:
                styled_qr = self._add_text_overlay(styled_qr, style_config['text_overlay'])
            
            # Apply effects
            if 'effects' in style_config:
                styled_qr = self._apply_effects(styled_qr, style_config['effects'])
            
            # Add rounded corners
            if 'rounded_corners' in style_config:
                styled_qr = self._add_rounded_corners(
                    styled_qr, 
                    style_config['rounded_corners'].get('radius', 20)
                )
            
            return styled_qr
            
        except Exception as e:
            logger.error(f"Failed to apply QR style: {e}")
            return qr_image
    
    def _apply_colors(self, qr_image: Image.Image, colors: Dict[str, str]) -> Image.Image:
        """Apply custom colors to QR code"""
        
        foreground = colors.get('foreground', 'black')
        background = colors.get('background', 'white')
        
        # Convert color names to RGB
        fg_rgb = self._color_to_rgb(foreground)
        bg_rgb = self._color_to_rgb(background)
        
        # Create new image with custom colors
        pixels = qr_image.load()
        
        for i in range(qr_image.size[0]):
            for j in range(qr_image.size[1]):
                pixel = pixels[i, j]
                
                # Determine if pixel is foreground or background
                # QR codes use pure black/white, so we check brightness
                brightness = sum(pixel) / 3
                
                if brightness < 128:  # Dark pixel (foreground)
                    pixels[i, j] = fg_rgb
                else:  # Light pixel (background)
                    pixels[i, j] = bg_rgb
        
        return qr_image
    
    def _apply_pattern(self, qr_image: Image.Image, pattern_config: Dict[str, Any]) -> Image.Image:
        """Apply pattern overlay to QR code"""
        
        pattern_type = pattern_config.get('type', 'dots')
        pattern_color = pattern_config.get('color', '#cccccc')
        pattern_size = pattern_config.get('size', 2)
        
        if pattern_type == 'dots':
            return self._apply_dots_pattern(qr_image, pattern_color, pattern_size)
        elif pattern_type == 'lines':
            return self._apply_lines_pattern(qr_image, pattern_color, pattern_size)
        elif pattern_type == 'gradient':
            return self._apply_gradient_pattern(qr_image, pattern_config)
        else:
            return qr_image
    
    def _apply_dots_pattern(self, qr_image: Image.Image, color: str, size: int) -> Image.Image:
        """Apply dots pattern to background"""
        
        pattern_rgb = self._color_to_rgb(color)
        pixels = qr_image.load()
        
        for i in range(0, qr_image.size[0], size * 2):
            for j in range(0, qr_image.size[1], size * 2):
                # Check if this is a background pixel
                if sum(pixels[i, j]) / 3 > 200:  # Light background
                    # Draw a small dot
                    for di in range(-size//2, size//2 + 1):
                        for dj in range(-size//2, size//2 + 1):
                            if (0 <= i+di < qr_image.size[0] and 
                                0 <= j+dj < qr_image.size[1]):
                                if sum(pixels[i+di, j+dj]) / 3 > 200:
                                    pixels[i+di, j+dj] = pattern_rgb
        
        return qr_image
    
    def _apply_lines_pattern(self, qr_image: Image.Image, color: str, spacing: int) -> Image.Image:
        """Apply lines pattern to background"""
        
        pattern_rgb = self._color_to_rgb(color)
        pixels = qr_image.load()
        
        # Vertical lines
        for i in range(0, qr_image.size[0], spacing):
            for j in range(qr_image.size[1]):
                if sum(pixels[i, j]) / 3 > 200:  # Light background
                    pixels[i, j] = pattern_rgb
        
        return qr_image
    
    def _apply_gradient_pattern(self, qr_image: Image.Image, config: Dict[str, Any]) -> Image.Image:
        """Apply gradient pattern to background"""
        
        start_color = config.get('start_color', '#ffffff')
        end_color = config.get('end_color', '#f0f0f0')
        direction = config.get('direction', 'vertical')
        
        start_rgb = self._color_to_rgb(start_color)
        end_rgb = self._color_to_rgb(end_color)
        
        pixels = qr_image.load()
        width, height = qr_image.size
        
        for i in range(width):
            for j in range(height):
                if sum(pixels[i, j]) / 3 > 200:  # Light background
                    # Calculate gradient position
                    if direction == 'vertical':
                        ratio = j / height
                    else:  # horizontal
                        ratio = i / width
                    
                    # Interpolate color
                    gradient_color = tuple(
                        int(start_rgb[k] + (end_rgb[k] - start_rgb[k]) * ratio)
                        for k in range(3)
                    )
                    
                    pixels[i, j] = gradient_color
        
        return qr_image
    
    def _add_frame(self, qr_image: Image.Image, frame_config: Dict[str, Any]) -> Image.Image:
        """Add frame/border to QR code"""
        
        frame_width = frame_config.get('width', 10)
        frame_color = frame_config.get('color', '#000000')
        frame_style = frame_config.get('style', 'solid')
        
        frame_rgb = self._color_to_rgb(frame_color)
        
        # Create new image with frame
        new_width = qr_image.size[0] + 2 * frame_width
        new_height = qr_image.size[1] + 2 * frame_width
        
        framed_qr = Image.new('RGB', (new_width, new_height), frame_rgb)
        
        # Paste QR in center
        framed_qr.paste(qr_image, (frame_width, frame_width))
        
        # Add decorative elements if needed
        if frame_style == 'rounded':
            framed_qr = self._add_rounded_corners(framed_qr, frame_width)
        elif frame_style == 'shadow':
            framed_qr = self._add_shadow_effect(framed_qr)
        
        return framed_qr
    
    def _add_logo(self, qr_image: Image.Image, logo_config: Dict[str, Any]) -> Image.Image:
        """Add logo to QR code"""
        
        logo_path = logo_config.get('path')
        if not logo_path or not os.path.exists(logo_path):
            return qr_image
        
        try:
            logo = Image.open(logo_path)
            
            # Calculate logo size
            qr_size = qr_image.size[0]
            logo_size_ratio = logo_config.get('size_ratio', 0.2)
            logo_size = int(qr_size * logo_size_ratio)
            
            # Resize logo
            logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
            
            # Add white background for logo if needed
            if logo_config.get('white_background', True):
                logo_bg = Image.new('RGB', (logo_size + 10, logo_size + 10), 'white')
                logo_bg.paste(logo, (5, 5), logo if logo.mode == 'RGBA' else None)
                logo = logo_bg
                logo_size += 10
            
            # Calculate position
            logo_pos = ((qr_size - logo_size) // 2, (qr_size - logo_size) // 2)
            
            # Paste logo
            qr_image.paste(logo, logo_pos, logo if logo.mode == 'RGBA' else None)
            
        except Exception as e:
            logger.error(f"Failed to add logo: {e}")
        
        return qr_image
    
    def _add_text_overlay(self, qr_image: Image.Image, text_config: Dict[str, Any]) -> Image.Image:
        """Add text overlay to QR code"""
        
        text = text_config.get('text', '')
        if not text:
            return qr_image
        
        font_size = text_config.get('font_size', 20)
        font_color = text_config.get('color', '#000000')
        position = text_config.get('position', 'bottom')
        
        try:
            # Load font
            font = self._get_font(font_size)
            
            # Create text image
            draw = ImageDraw.Draw(qr_image)
            text_rgb = self._color_to_rgb(font_color)
            
            # Calculate text position
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            if position == 'bottom':
                # Add space at bottom
                new_image = Image.new('RGB', 
                    (qr_image.size[0], qr_image.size[1] + text_height + 20), 'white')
                new_image.paste(qr_image, (0, 0))
                
                draw = ImageDraw.Draw(new_image)
                text_x = (new_image.size[0] - text_width) // 2
                text_y = qr_image.size[1] + 10
                
                draw.text((text_x, text_y), text, font=font, fill=text_rgb)
                
                return new_image
            
            elif position == 'top':
                # Add space at top
                new_image = Image.new('RGB', 
                    (qr_image.size[0], qr_image.size[1] + text_height + 20), 'white')
                new_image.paste(qr_image, (0, text_height + 20))
                
                draw = ImageDraw.Draw(new_image)
                text_x = (new_image.size[0] - text_width) // 2
                text_y = 10
                
                draw.text((text_x, text_y), text, font=font, fill=text_rgb)
                
                return new_image
            
            else:  # overlay on QR
                text_x = (qr_image.size[0] - text_width) // 2
                text_y = (qr_image.size[1] - text_height) // 2
                
                # Add white background for text
                padding = 5
                draw.rectangle([
                    text_x - padding, text_y - padding,
                    text_x + text_width + padding, text_y + text_height + padding
                ], fill='white')
                
                draw.text((text_x, text_y), text, font=font, fill=text_rgb)
                
                return qr_image
                
        except Exception as e:
            logger.error(f"Failed to add text overlay: {e}")
            return qr_image
    
    def _apply_effects(self, qr_image: Image.Image, effects_config: Dict[str, Any]) -> Image.Image:
        """Apply visual effects to QR code"""
        
        effects = effects_config.get('types', [])
        
        for effect in effects:
            if effect == 'blur':
                blur_radius = effects_config.get('blur_radius', 1)
                qr_image = qr_image.filter(ImageFilter.GaussianBlur(radius=blur_radius))
            
            elif effect == 'sharpen':
                qr_image = qr_image.filter(ImageFilter.SHARPEN)
            
            elif effect == 'emboss':
                qr_image = qr_image.filter(ImageFilter.EMBOSS)
            
            elif effect == 'vintage':
                qr_image = self._apply_vintage_effect(qr_image)
        
        return qr_image
    
    def _apply_vintage_effect(self, qr_image: Image.Image) -> Image.Image:
        """Apply vintage effect to QR code"""
        
        # Add sepia tone
        pixels = qr_image.load()
        
        for i in range(qr_image.size[0]):
            for j in range(qr_image.size[1]):
                r, g, b = pixels[i, j]
                
                # Sepia transformation
                new_r = min(255, int(r * 0.393 + g * 0.769 + b * 0.189))
                new_g = min(255, int(r * 0.349 + g * 0.686 + b * 0.168))
                new_b = min(255, int(r * 0.272 + g * 0.534 + b * 0.131))
                
                pixels[i, j] = (new_r, new_g, new_b)
        
        return qr_image
    
    def _add_rounded_corners(self, qr_image: Image.Image, radius: int = 20) -> Image.Image:
        """Add rounded corners to image"""
        
        # Create mask
        mask = Image.new('L', qr_image.size, 0)
        draw = ImageDraw.Draw(mask)
        
        # Draw rounded rectangle
        draw.rounded_rectangle([(0, 0), qr_image.size], radius=radius, fill=255)
        
        # Apply mask
        if qr_image.mode != 'RGBA':
            qr_image = qr_image.convert('RGBA')
        
        qr_image.putalpha(mask)
        
        return qr_image
    
    def _add_shadow_effect(self, qr_image: Image.Image, offset: int = 5, blur: int = 5) -> Image.Image:
        """Add shadow effect to image"""
        
        # Create shadow
        shadow = Image.new('RGB', qr_image.size, 'gray')
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=blur))
        
        # Create new image with shadow
        new_size = (qr_image.size[0] + offset, qr_image.size[1] + offset)
        new_image = Image.new('RGB', new_size, 'white')
        
        # Paste shadow and image
        new_image.paste(shadow, (offset, offset))
        new_image.paste(qr_image, (0, 0))
        
        return new_image
    
    def _color_to_rgb(self, color: str) -> Tuple[int, int, int]:
        """Convert color name/hex to RGB tuple"""
        
        # Named colors
        color_map = {
            'black': (0, 0, 0),
            'white': (255, 255, 255),
            'red': (255, 0, 0),
            'green': (0, 255, 0),
            'blue': (0, 0, 255),
            'yellow': (255, 255, 0),
            'purple': (128, 0, 128),
            'orange': (255, 165, 0),
            'pink': (255, 192, 203),
            'cyan': (0, 255, 255),
            'magenta': (255, 0, 255),
            'lime': (0, 255, 0),
            'navy': (0, 0, 128),
            'teal': (0, 128, 128),
            'brown': (165, 42, 42),
            'gray': (128, 128, 128),
            'grey': (128, 128, 128),
        }
        
        if color.lower() in color_map:
            return color_map[color.lower()]
        
        # Hex color
        if color.startswith('#'):
            try:
                hex_color = color.lstrip('#')
                if len(hex_color) == 3:
                    hex_color = ''.join([c*2 for c in hex_color])
                return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            except:
                pass
        
        # RGB tuple string
        if color.startswith('(') and color.endswith(')'):
            try:
                return tuple(map(int, color.strip('()').split(',')))
            except:
                pass
        
        # Default to black
        return (0, 0, 0)
    
    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:
        """Get font for text rendering"""
        
        try:
            # Try to load a system font
            font_paths = [
                '/System/Library/Fonts/Arial.ttf',  # macOS
                '/Windows/Fonts/arial.ttf',       # Windows
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',  # Linux
            ]
            
            for font_path in font_paths:
                if os.path.exists(font_path):
                    return ImageFont.truetype(font_path, size)
            
            # Fallback to default font
            return ImageFont.load_default()
            
        except:
            return ImageFont.load_default()
    
    def _load_default_templates(self) -> Dict[str, Dict[str, Any]]:
        """Load default QR styling templates"""
        
        return {
            'professional': {
                'name': 'Professional',
                'description': 'Clean and professional look',
                'config': {
                    'colors': {
                        'foreground': '#1a1a1a',
                        'background': '#ffffff'
                    },
                    'frame': {
                        'width': 15,
                        'color': '#f0f0f0',
                        'style': 'solid'
                    },
                    'rounded_corners': {'radius': 10}
                }
            },
            
            'colorful': {
                'name': 'Colorful',
                'description': 'Bright and colorful design',
                'config': {
                    'colors': {
                        'foreground': '#ff6b6b',
                        'background': '#4ecdc4'
                    },
                    'pattern': {
                        'type': 'dots',
                        'color': '#ffe66d',
                        'size': 3
                    },
                    'rounded_corners': {'radius': 25}
                }
            },
            
            'business': {
                'name': 'Business',
                'description': 'Corporate style with logo support',
                'config': {
                    'colors': {
                        'foreground': '#2c3e50',
                        'background': '#ecf0f1'
                    },
                    'frame': {
                        'width': 20,
                        'color': '#34495e',
                        'style': 'solid'
                    },
                    'text_overlay': {
                        'text': 'Scan Me',
                        'position': 'bottom',
                        'font_size': 16,
                        'color': '#2c3e50'
                    }
                }
            },
            
            'modern': {
                'name': 'Modern',
                'description': 'Contemporary gradient design',
                'config': {
                    'pattern': {
                        'type': 'gradient',
                        'start_color': '#667eea',
                        'end_color': '#764ba2',
                        'direction': 'vertical'
                    },
                    'colors': {
                        'foreground': '#ffffff',
                        'background': 'transparent'
                    },
                    'effects': {
                        'types': ['blur'],
                        'blur_radius': 0.5
                    }
                }
            },
            
            'vintage': {
                'name': 'Vintage',
                'description': 'Retro sepia tone effect',
                'config': {
                    'colors': {
                        'foreground': '#8b4513',
                        'background': '#f5deb3'
                    },
                    'frame': {
                        'width': 25,
                        'color': '#d2691e',
                        'style': 'solid'
                    },
                    'effects': {
                        'types': ['vintage']
                    },
                    'rounded_corners': {'radius': 15}
                }
            }
        }
    
    def get_template(self, template_name: str) -> Optional[Dict[str, Any]]:
        """Get styling template by name"""
        
        return self.templates.get(template_name)
    
    def list_templates(self) -> List[Dict[str, str]]:
        """List all available templates"""
        
        return [
            {
                'name': template['name'],
                'description': template['description'],
                'id': template_id
            }
            for template_id, template in self.templates.items()
        ]
    
    def create_custom_template(self, name: str, description: str, 
                            config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a custom styling template"""
        
        template_id = name.lower().replace(' ', '_')
        
        self.templates[template_id] = {
            'name': name,
            'description': description,
            'config': config,
            'custom': True
        }
        
        return {
            'success': True,
            'template_id': template_id,
            'message': 'Custom template created successfully'
        }


# Global instance
qr_styler = QRStyler()
