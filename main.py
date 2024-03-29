import os
import time
from typing import List

import psMat
from tortoise import Tortoise
from nicegui import app, ui, events
from lxml import etree
import utils
import models
import fontforge
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import FileResponse


async def init_db() -> None:
    # 判断 data 目录是否存在，不存在则创建
    if not os.path.exists("data"):
        os.makedirs("data")

    await Tortoise.init(db_url="sqlite://data/db.sqlite3", modules={"models": ["models"]})
    await Tortoise.generate_schemas()

    # 创建默认项目
    if not await models.Project.exists():
        await models.Project.create(name="默认项目")

    # 创建默认用户
    if not await models.User.exists():
        username = os.getenv("TOOL_ADMIN_USERNAME", "admin")
        password = os.getenv("TOOL_ADMIN_PASSWORD", "admin")
        await models.User.create(username=username, password=password)


async def close_db() -> None:
    await Tortoise.close_connections()


app.on_startup(init_db)
app.on_shutdown(close_db)

security = HTTPBasic()


async def authorize(creds: HTTPBasicCredentials = Depends(security)):
    username = creds.username
    password = creds.password

    # 查询数据库是否存在此用户
    user = await models.User.filter(username=username, password=password).first()
    if user:
        return True
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )


@ui.refreshable
async def list_of_projects() -> None:
    projects: List[models.Project] = await models.Project.all().prefetch_related("icons")

    with ui.dialog() as dialog, ui.card().classes("w-[300px]"):
        ui.label("⚠️ 警告").classes("text-xl font-bold")
        ui.label("删除项目将会同时删除项目中所有图标，确认要删除吗？")
        with ui.row().classes("w-full items-center justify-end mt-4"):
            ui.button("删除", on_click=lambda: dialog.submit(True)).props('color="deep-orange"')
            ui.button("取消", on_click=lambda: dialog.submit(False))

    async def delete(p: models.Project) -> None:
        result = await dialog
        if result is True:
            # 删除项目与项目中的图标
            await models.Icon.filter(project_id=p.id).delete()
            await models.Project.filter(id=p.id).delete()
            list_of_projects.refresh()

    with ui.row().classes("w-full flex-wrap"):
        for project in reversed(projects):
            with ui.card().classes("w-[320px] overflow-hidden"):
                ui.label(project.name).classes("text-xl")
                # 图标数量
                ui.label(f"图标数量: {len(project.icons)}")
                # 操作按钮，查看和删除
                with ui.row().classes("w-full items-center justify-end"):
                    ui.button(icon="visibility", on_click=lambda p=project: ui.open(f"/project/{p.id}")).props(
                        'flat round color="blue"'
                    )
                    ui.button(icon="delete", on_click=lambda p=project: delete(p)).props(
                        'flat round color="deep-orange"'
                    )


@ui.refreshable
async def list_of_icons(p: models.Project) -> None:
    icons: List[models.Icon] = await models.Icon.filter(project_id=p.id).all()

    with ui.dialog() as dialog, ui.card().classes("w-[300px]"):
        ui.label("⚠️ 警告").classes("text-xl font-bold")
        ui.label("确认要删除此图标吗？")
        with ui.row().classes("w-full items-center justify-end mt-4"):
            ui.button("删除", on_click=lambda: dialog.submit(True)).props('color="deep-orange"')
            ui.button("取消", on_click=lambda: dialog.submit(False))

    async def delete(i: models.Icon) -> None:
        result = await dialog
        if result is True:
            await i.delete()
            list_of_icons.refresh()

    ui.label(f"图标数量: {len(icons)}")
    with ui.row().classes("w-full"):
        for icon in reversed(icons):
            with ui.card().classes("w-[250px] overflow-hidden"):
                with ui.row().classes("w-full items-center flex-nowrap"):
                    ui.html(icon.content).classes("w-8 h-8")
                    with ui.column().classes("flex-1 overflow-hidden"):
                        ui.label(icon.name).classes("w-full truncate")
                        with ui.row().classes("w-full items-center justify-between"):
                            ui.label(icon.unicode()).classes("text-xs")
                            ui.button(icon="delete", on_click=lambda i=icon: delete(i)).props(
                                'flat round color="deep-orange" size="xs"'
                            )


refresh_icons = utils.Debounce(list_of_icons.refresh, 0.5)


# 处理 svg 内容，去掉颜色，宽高，去掉所有 path 中的 fill
def handle_svg_content(content):
    root = etree.XML(content)
    for node in root.xpath("//*"):
        node.attrib.pop("fill", None)
        node.attrib.pop("width", None)
        node.attrib.pop("height", None)
        # 每个path下的 fill 都需要去掉
        for path in node.xpath("path"):
            path.attrib.pop("fill", None)

    return etree.tostring(root, encoding="unicode")


async def handle_upload(e: events.UploadEventArguments, p: models.Project):
    # 读取出 svg 文件
    name = e.name.split(".")[0]
    content = e.content.read().decode("utf-8")
    content = handle_svg_content(content)

    # 判断 name 是否存在, 如果存在，则修改，否则新增
    icon = await models.Icon.filter(project_id=p.id, name=name).first()
    if icon:
        # 更新
        icon.content = content
        await icon.save()
    else:
        # 新增
        await models.Icon.create(project_id=p.id, name=name, content=content)

        await p.save()

    refresh_icons()


async def generate_dart(p: models.Project):
    icons = await models.Icon.filter(project_id=p.id).all()
    if not icons:
        ui.notify("没有图标")
        return

    dart_str = "import 'package:flutter/material.dart';\\n\\n"
    dart_str += "// ignore_for_file: constant_identifier_names\\n"
    dart_str += "class AppIcons {\\n"
    dart_str += "  AppIcons._();\\n\\n"

    for item in icons:
        dart_str += (
            f"  static const IconData {item.name} = IconData(0x{item.unicode()[2:]}, fontFamily: 'IconFont'); \\n"
        )

    dart_str += "}\\n"

    await ui.run_javascript(
        f"""
        var textarea = document.createElement("textarea");
        textarea.value = "{dart_str}";
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
        """
    )

    ui.notify("已复制到剪切板")


async def generate_css(p: models.Project):
    icons = await models.Icon.filter(project_id=p.id).all()
    if not icons:
        ui.notify("没有图标")
        return

    # 当前时间戳
    timestamp = int(round(time.time() * 1000))

    css_str = "@font-face {\\n"
    css_str += '  font-family: "iconfont";\\n'
    css_str += f'  url("iconfont.ttf?t={timestamp}") format("truetype");\\n'
    css_str += "}\\n\\n"
    css_str += ".iconfont {\\n"
    css_str += '  font-family: "iconfont" !important;\\n'
    css_str += "  font-size: 16px;\\n"
    css_str += "  font-style: normal;\\n"
    css_str += "  line-height: 1;\\n"
    css_str += "  -webkit-font-smoothing: antialiased;\\n"
    css_str += "  -moz-osx-font-smoothing: grayscale;\\n"
    css_str += "}\\n\\n"

    for item in icons:
        css_str += f'.{item.name}::before {{ content: "\\\\{item.unicode()[2:]}"; }}\\n\\n'

    await ui.run_javascript(
        f"""
        var textarea = document.createElement("textarea");
        textarea.value = '{css_str}';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
        """
    )

    ui.notify("已复制到剪切板")


async def generate_swift(p: models.Project):
    icons = await models.Icon.filter(project_id=p.id).all()
    if not icons:
        ui.notify("没有图标")
        return

    swift_str = """import Foundation\\n\\npublic enum AppIcons {\\n\\n"""

    for item in icons:
        swift_str += f'  public static let {item.name} = "'
        swift_str += "\\\\u{"
        swift_str += item.unicode()[2:]
        swift_str += '}"\\n\\n'

    swift_str += "}\\n"

    await ui.run_javascript(
        f"""
        var textarea = document.createElement("textarea");
        textarea.value = '{swift_str}';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
        """
    )

    ui.notify("已复制到剪切板")


@ui.page("/", dependencies=[Depends(authorize)])
async def index():
    # 创建项目的对话框
    with ui.dialog() as dialog, ui.card().classes("w-[350px]"):
        ui.label("创建项目").classes("text-xl font-bold")
        i = ui.input(placeholder="输入项目名称").props("outlined clearable").classes("w-full")
        with ui.row().classes("w-full items-center justify-end mt-4"):
            ui.button("创建", on_click=lambda: dialog.submit(i.value))
            ui.button("取消", on_click=lambda: dialog.submit(False))

    async def create_project() -> None:
        result = await dialog
        if result is not False:
            await models.Project.create(name=result)
            list_of_projects.refresh()

    with ui.row():
        ui.label("项目列表").classes("text-3xl")
        ui.button("创建项目", on_click=create_project)
    await list_of_projects()


# 项目详情
@ui.page("/project/{project_id}", dependencies=[Depends(authorize)])
async def project_detail(project_id: int):
    project = await models.Project.get_or_none(id=project_id)
    if project is None:
        return ui.label("项目不存在")

    ui.add_head_html(
        """
    <style>
    .q-uploader__list{
        display: none;
    }
    </style>
    """
    )

    with ui.row().classes("w-full items-center"):
        ui.button(icon="home", on_click=lambda p=project: ui.open("/")).props('flat round color="blue"')
        ui.label("项目：" + project.name).classes("text-3xl")
        ui.upload(
            multiple=True, label="上传图标", on_upload=lambda e: handle_upload(e, project), auto_upload=True
        ).props("accept=.svg").style("width: 210px")
        ui.button("下载字体文件", on_click=lambda p=project: ui.open(f"/download/{p.id}")).style("height: 52px")
        ui.button("复制dart", on_click=lambda p=project: generate_dart(p)).style("height: 52px")
        ui.button("复制css", on_click=lambda p=project: generate_css(p)).style("height: 52px")
        ui.button("复制swift", on_click=lambda p=project: generate_swift(p)).style("height: 52px")

    await list_of_icons(project)


@app.get(path="/download/{project_id}", dependencies=[Depends(authorize)])
async def download_ttf(project_id):
    icons = await models.Icon.filter(project_id=project_id).all()
    if not icons:
        return

    # 获取当前 project 根目录
    root_path = os.path.dirname(os.path.abspath(__file__))

    build_path = os.path.join(root_path, "build")

    svg_path = os.path.join(build_path, "svg")

    ttf_path = os.path.join(build_path, "iconfont.ttf")

    # 把每个 icon 的 content 写入到 build/svg/name.svg

    # 判断 build/svg 是否存在，不存在则创建，存在则清空
    if not os.path.exists(svg_path):
        os.makedirs(svg_path)
    else:
        for file in os.listdir(svg_path):
            os.remove(os.path.join(svg_path, file))

    # 如果存在 build/iconfont.ttf 则删除
    if os.path.exists(ttf_path):
        os.remove(ttf_path)

    # 创建新字体
    font = fontforge.font()
    font.encoding = "UnicodeFull"
    font.familyname = "iconfont"
    font.fullname = "iconfont"
    font.fontname = "iconfont"
    
    font.em = 1000
    font.ascent = 800
    font.descent = 200

    # 计算垂直居中的位置
    vcenter = (font.ascent - font.descent / 2) / 2

    for icon in icons:
        icon_path = os.path.join(svg_path, f"{icon.name}.svg")
        with open(icon_path, "w") as f1:
            f1.write(icon.content)

        glyph = font.createChar(int(icon.unicode(), 16))
        glyph.importOutlines(icon_path, ('removeoverlap', 'correctdir'))
        glyph.removeOverlap()

        # 指定字体名称
        glyph.glyphname = icon.name
        # 设置字体的宽度
        glyph.width = 1000

        # 垂直居中
        bounding = glyph.boundingBox()  # xmin,ymin,xmax,ymax
        glyphcenter = (bounding[3] - bounding[1]) / 2 + bounding[1]
        deltay = vcenter - glyphcenter
        matrix = psMat.translate(0, deltay)
        glyph.transform(matrix)

    # 保存字体文件
    font.generate(ttf_path)

    return FileResponse(path=ttf_path, filename="iconfont.ttf", media_type="application/octet-stream")


ui.run(title="iconfont 管理工具", favicon="🚀")
