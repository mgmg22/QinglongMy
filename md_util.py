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

    # 处理带链接的标题 (##### [time text](url) )
    def replace_title_with_link(match):
        time_text = match.group(1)
        link_text = match.group(2)
        url = match.group(3)
        return f'<h5 style="margin-bottom: 5px;"><a href="{url}">{time_text} {link_text}</a></h5>'

    # 处理标题
    def replace_heading(match):
        level = len(match.group(1))
        text = match.group(2)
        return f'<h{level} style="margin-bottom: 5px;">{text}</h{level}>'

    # 处理图片
    def replace_image(match):
        url = match.group(1)
        return f'<img style="max-width: 100%; margin: 5px 0;" src="{url}" />'

    # 处理评分
    def replace_score(match):
        score = match.group(1)
        return f'<p style="margin-top: 5px; color: gray;">「评分{score}分」{match.group(2)}</p>'

    # 替换带链接的标题
    md_text = re.sub(r'#####\s*\[([^\]]+)\s*([^\]]+)\]\(([^)]+)\)', replace_title_with_link, md_text)
    # 替换标题
    md_text = re.sub(r'(#+)\s*(.+)', replace_heading, md_text)
    # 替换图片
    md_text = re.sub(r'!\[\]\(([^)]+)\)', replace_image, md_text)
    # 替换评分
    md_text = re.sub(r'「评分(\d+)分」(.+)', replace_score, md_text)
    # 转换剩余Markdown
    html = markdown.markdown(md_text)

    # 添加一些基础样式
    html = f"<div style='font-family: sans-serif; line-height: 1.6;'>{html}</div>"
    return html
