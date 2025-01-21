import markdown
import re


def markdown_to_html(md_text):
    """
    将包含特殊格式的 Markdown 文本转换为 HTML。
    Args:
        md_text (str): 包含特殊格式的 Markdown 文本。
    Returns:
        str: 转换后的 HTML 文本。
    """

    # 处理5个#号的标题，包括带链接和不带链接的形式
    def replace_heading(match):
        if match.group(2):  # 带链接的标题
            time_text = match.group(2)
            link_text = match.group(3)
            url = match.group(4)
            return f'<h5 style="margin-bottom: 5px;"><a href="{url}">{time_text} {link_text}</a></h5>'
        else:  # 普通标题
            text = match.group(1)
            return f'<h5 style="margin-bottom: 5px;">{text}</h5>'

    # 处理图片
    def replace_image(match):
        url = match.group(1)
        return f'<img style="max-width: 100%; margin: 5px 0;" src="{url}" />'

    # 处理评分
    def replace_score(match):
        score = match.group(1)
        return f'<p style="margin-top: 5px; color: gray;">「评分{score}分」{match.group(2)}</p>'

    # 处理小程序链接
    def replace_miniprogram(match):
        url = match.group(1)
        return f'<span class="miniprogram-text">#小程序://{url}</span>'

    # 替换小程序链接（需要在标题处理之前）
    md_text = re.sub(r'#小程序://([^\s]+)', replace_miniprogram, md_text)
    # 替换标题（同时处理带链接和不带链接的形式）
    md_text = re.sub(
        r'#{5}\s+(?:\[([^\]]+)\s*([^\]]+)\]\(([^)]+)\)|(.+))',
        replace_heading,
        md_text
    )
    # 替换图片
    md_text = re.sub(r'!\[\]\(([^)]+)\)', replace_image, md_text)
    # 替换评分
    md_text = re.sub(r'「评分(\d+)分」(.+)', replace_score, md_text)
    # 转换剩余Markdown
    html = markdown.markdown(md_text)

    # 添加一些基础样式
    html = f"<div style='font-family: sans-serif; line-height: 1.6;'>{html}</div>"
    return html
