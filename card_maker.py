
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
import os

def generate_card(pfp_path, sub_number, sub_name="Anon", output_path="custom_card.png",
        grain_strength=0.1, grain_sigma=80,
        font_path="/Library/Fonts/Helvetica.ttc"):

    # if user uploads pfp
    if pfp_path:

        subject_pos=(326, 345)
        name_pos=(245, 409)
        subject_font_size=41
        name_font_size=39

        tpl = Image.open("Chain_of_trust_template.png").convert("RGBA")
        pfp = Image.open(pfp_path).convert("RGBA")  
        bbox=(674, 262, 887, 476)
        x1, y1, x2, y2 = bbox
        width = x2 - x1
        height = y2 - y1
        diameter = min(width, height)
        paste_x = x1 + (width - diameter)//2
        paste_y = y1 + (height - diameter)//2

        pfp_square = ImageOps.fit(pfp, (diameter, diameter), method=Image.LANCZOS, centering=(0.5, 0.5))

        # create grain and blend it with pfp
        if grain_strength and grain_strength > 0:
            base_rgb = pfp_square.convert("RGB")
            noise = Image.effect_noise(base_rgb.size, grain_sigma).convert("L")
            # make noise RGB and blend
            noise_rgb = Image.merge("RGB", (noise, noise, noise))
            blended = Image.blend(base_rgb, noise_rgb, float(grain_strength))
            # reattach alpha from the square pfp
            alpha = pfp_square.split()[-1]
            blended.putalpha(alpha)
            pfp_square = blended

        # making circular mask
        mask = Image.new("L", (diameter, diameter), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, diameter, diameter), fill=255)
        pfp_square.putalpha(mask)  
        tpl.paste(pfp_square, (paste_x, paste_y), pfp_square)
        
        # draw text
        draw_tpl = ImageDraw.Draw(tpl)
        try:
            font_subject = ImageFont.truetype(font_path, subject_font_size)
            font_name = ImageFont.truetype(font_path, name_font_size)
        except Exception:
            # size ignored for default font
            font_subject = ImageFont.load_default()
            font_name = ImageFont.load_default()

        white = (255, 240, 230, 255)
        stroke_width = 1

        # draw text 
        draw_tpl.text(subject_pos, str('#' + sub_number), font=font_subject, fill=white, stroke_width=stroke_width, stroke_fill=white)
        draw_tpl.text(name_pos, str(sub_name), font=font_name,  fill=white, stroke_width=stroke_width, stroke_fill=(0,0,0,255))
        tpl.save(output_path)
        return output_path
    
    #if user dont provide pfp
    else:
        subject_pos=(435, 415)
        name_pos=(320, 495)
        subject_font_size=50
        name_font_size=50
        tpl = Image.open("Chain_of_trust_anon.png").convert("RGBA")
        draw_tpl = ImageDraw.Draw(tpl)
        #try:
        font_subject = ImageFont.truetype(font_path, subject_font_size)
        font_name = ImageFont.truetype(font_path, name_font_size)
        white = (255, 240, 230, 255)
        stroke_width = 1

        # draw text 
        #subject number
        draw_tpl.text(subject_pos, str('#' + sub_number), font=font_subject, fill=white, stroke_width=stroke_width, stroke_fill=white)
        # subject name
        draw_tpl.text(name_pos, str(sub_name), font=font_name,  fill=white, stroke_width=stroke_width, stroke_fill=(0,0,0,255))

        tpl.save(output_path)
        return output_path

