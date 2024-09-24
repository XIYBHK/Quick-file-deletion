import os
import sys
import shutil
import logging
from typing import List, Optional
import tkinter as tk
from tkinter import messagebox, ttk
from tkinterdnd2 import DND_FILES, TkinterDnD
from datetime import datetime
import asyncio
import re  # 添加这行导入语句

VERSION = "1.9.1"

def resource_path(relative_path):
    """ 获取资源绝对路径 """
    try:
        # PyInstaller 创建临时文件夹 _MEIxxxxxx
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_write_path(filename):
    """获取可写的文件路径"""
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), filename)
    else:
        return os.path.join(os.path.abspath("."), filename)

log_file = get_write_path("delete_file.log")
HISTORY_FILE = get_write_path("delete_history.txt")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def delete_file_or_directory(path: str, force: bool = True, verbose: bool = True, recursive: bool = True) -> Optional[str]:
    path = path.strip('{}')
    if not os.path.exists(path):
        logger.warning(f"路径 {path} 不存在")
        return None

    try:
        if os.path.isfile(path):
            os.remove(path)
            if verbose:
                logger.info(f"文件 {path} 已删除")
            return add_to_history(os.path.basename(path), "文件")
        elif os.path.isdir(path):
            file_list = []
            if recursive:
                for root, _, files in os.walk(path):
                    file_list.extend(files)
                shutil.rmtree(path)
                if verbose:
                    logger.info(f"目录 {path} 及其内容已删除")
            else:
                file_list = os.listdir(path)
                os.rmdir(path)
                if verbose:
                    logger.info(f"空目录 {path} 已删除")
            return add_to_history(os.path.basename(path), "目录", file_list)
    except Exception as e:
        logger.error(f"删除 {path} 时出错: {e}")
        return None

def add_to_history(name: str, type: str, file_list: Optional[List[str]] = None) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    history_entry = f"{timestamp}|{type}|{name}"
    if file_list:
        history_entry += f"|{','.join(file_list)}"
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(history_entry + "\n")
    return history_entry

def shorten_path(path: str, max_length: int = 40) -> str:
    if len(path) <= max_length:
        return path
    parts = path.split(os.sep)
    if len(parts) > 3:
        return os.path.join(parts[0], '...', parts[-2], parts[-1])
    return '...' + path[-(max_length-3):]

# 1. 定义常量
WINDOW_WIDTH = 600
WINDOW_HEIGHT = 550
FONT_SIZE = 12
MAX_PATH_LENGTH = 40

class DeleteFileGUI:
    def __init__(self, master):
        self.master = master
        master.title("快速删除工具")
        master.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")

        self._create_widgets()

    def _create_widgets(self):
        self._create_drop_area()
        self._create_warning_label()
        self._create_history_section()

    def _create_drop_area(self):
        self.drop_area = tk.Canvas(self.master, width=580, height=150, bg="lightgray")
        self.drop_area.pack(pady=10, padx=10)
        self.drop_area.create_text(290, 75, text="将文件拖放到这里快速删除", fill="darkgray", font=("Arial", FONT_SIZE))
        self.drop_area.drop_target_register(DND_FILES)
        self.drop_area.dnd_bind('<<Drop>>', self.drop)

    def _create_warning_label(self):
        warning_frame = tk.Frame(self.master, bg="red", padx=5, pady=5)
        warning_frame.pack(pady=10, padx=10, fill=tk.X)
        warning_text = "警告：该删除方式不进入回收站\n文件将被直接删除且无法恢复！"
        tk.Label(warning_frame, text=warning_text, fg="white", bg="red",
                 wraplength=560, font=("Arial", FONT_SIZE, "bold"), justify=tk.CENTER).pack()

    def _create_history_section(self):
        history_frame = tk.Frame(self.master)
        history_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        self._create_history_header(history_frame)
        self._create_history_tree(history_frame)

    def _create_history_header(self, parent):
        header_frame = tk.Frame(parent)
        header_frame.pack(fill=tk.X)
        tk.Label(header_frame, text="删除历史：", font=("Arial", FONT_SIZE, "bold")).pack(side=tk.LEFT)
        tk.Button(header_frame, text="清空历史", command=self.clear_history).pack(side=tk.RIGHT)

    def _create_history_tree(self, parent):
        tree_frame = tk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.history_tree = ttk.Treeview(tree_frame, columns=("时间", "类型", "名称"), show="headings")
        for col, width in zip(("时间", "类型", "名称"), (140, 60, 380)):
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)

        self.history_tree.pack(side="left", fill=tk.BOTH, expand=True)
        scrollbar.pack(side="right", fill="y")

        self.history_tree.bind("<Double-1>", self.on_item_double_click)

        self.load_history()

    def drop(self, event):
        paths = [path.strip('{}').strip() for path in event.data.split('} {')]
        if not paths:
            return

        message = self._create_confirmation_message(paths)
        if messagebox.askyesno("确认永久删除", message, icon='warning'):
            asyncio.run(self._process_deletions(paths))

    def _create_confirmation_message(self, paths: List[str]) -> str:
        if len(paths) > 1:
            message = f"是否要永久删除以下 {len(paths)} 个文件/目录？\n" + "\n".join(shorten_path(path) for path in paths[:5])
            if len(paths) > 5:
                message += f"\n...以及其他 {len(paths) - 5} 个文件/目录"
        else:
            message = f"是否要永久删除 {shorten_path(paths[0])}？"
        return message + "\n\n警告：此操作将直接删除文件，不经过回收站，且无法恢复！"

    # 2. 使用异步方法处理文件删除
    async def _process_deletions(self, paths: List[str]):
        for path in paths:
            try:
                history_entry = await self._delete_file_or_directory_async(path)
                if history_entry:
                    self.update_history(history_entry)
                else:
                    messagebox.showerror("错误", f"无法删除 {shorten_path(path)}")
            except Exception as e:
                logger.error(f"删除文件时发生错误: {e}")
                messagebox.showerror("错误", f"删除 {shorten_path(path)} 时发生错误: {e}")
        messagebox.showinfo("完成", "删除操作已完成，文件已被永久删除。")

    # 3. 异步删除文件或目录
    async def _delete_file_or_directory_async(self, path: str) -> Optional[str]:
        # 这里使用 asyncio 来异步执行删除操作
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, delete_file_or_directory, path)

    def load_history(self):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        self.update_history(line.strip())
                    except ValueError as e:
                        logger.error(f"无法解析历史记录行: {line.strip()}. 错误: {e}")
        except FileNotFoundError:
            logger.info("历史文件不存在，将创建新的历史记录。")

    def update_history(self, entry: str):
        try:
            parts = entry.split('|')
            if len(parts) >= 3:
                time, type, name = parts[:3]
                file_list = parts[3].split(',') if len(parts) > 3 else []
                item = self.history_tree.insert("", 0, values=(time, type, name))
                if type == "目录" and file_list:
                    self.history_tree.item(item, tags=("has_preview",))
                    self.history_tree.tag_configure("has_preview", foreground="blue")
            else:
                logger.warning(f"历史记录格式不正确: {entry}")
        except Exception as e:
            logger.error(f"更新历史记录时出错: {entry}. 错误: {e}")

    def on_item_double_click(self, event):
        item = self.history_tree.selection()[0]
        item_type = self.history_tree.item(item, "values")[1]
        if item_type == "目录" and "has_preview" in self.history_tree.item(item, "tags"):
            self.show_directory_preview(item)

    def show_directory_preview(self, item):
        entry = self.history_tree.item(item, "values")
        time, type, name = entry
        self.file_list = self._get_file_list(time, type, name)

        preview_window = tk.Toplevel(self.master)
        preview_window.title(f"目录预览: {name}")
        preview_window.geometry("400x400")  # 增加窗口高度以容纳搜索框

        # 创建搜索框
        search_frame = tk.Frame(preview_window)
        search_frame.pack(fill=tk.X, padx=5, pady=5)
        tk.Label(search_frame, text="搜索:").pack(side=tk.LEFT)
        self.search_entry = tk.Entry(search_frame)
        self.search_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.search_entry.bind("<KeyRelease>", self.search_files)

        # 创建预览文本框
        self.preview_text = tk.Text(preview_window, wrap=tk.WORD)
        self.preview_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.update_preview()

    def update_preview(self, filtered_files=None):
        self.preview_text.config(state=tk.NORMAL)
        self.preview_text.delete(1.0, tk.END)
        self.preview_text.insert(tk.END, "目录中的文件：\n\n")
        
        files_to_display = filtered_files if filtered_files is not None else self.file_list
        for file in files_to_display:
            self.preview_text.insert(tk.END, f"- {file}\n")
        
        self.preview_text.config(state=tk.DISABLED)

    def search_files(self, event):
        search_term = self.search_entry.get().lower()
        if search_term:
            filtered_files = [file for file in self.file_list if re.search(search_term, file.lower())]
        else:
            filtered_files = self.file_list
        self.update_preview(filtered_files)

    def _get_file_list(self, time: str, type: str, name: str) -> List[str]:
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith(f"{time}|{type}|{name}"):
                        return line.strip().split('|')[3].split(',')
        except FileNotFoundError:
            logger.error(f"历史文件不存在: {HISTORY_FILE}")
        except Exception as e:
            logger.error(f"读取历史文件时出错: {e}")
        return []

    def clear_history(self):
        if messagebox.askyesno("确认", "是否确定要清空删除历史？"):
            try:
                os.remove(HISTORY_FILE)
            except FileNotFoundError:
                logger.warning(f"尝试删除不存在的历史文件: {HISTORY_FILE}")
            except Exception as e:
                logger.error(f"删除历史文件时出错: {e}")
            self.history_tree.delete(*self.history_tree.get_children())
            messagebox.showinfo("完成", "删除历史已清空")

# 4. 改进主函数
def main():
    try:
        setup_environment()
        root = TkinterDnD.Tk()
        gui = DeleteFileGUI(root)
        logger.info("程序启动")
        root.mainloop()
    except Exception as e:
        logger.exception("程序运行时出错")
        messagebox.showerror("错误", f"程序运行时出错: {e}\n请查看日志文件以获取更多信息。")

def setup_environment():
    dll_path = os.path.dirname(os.path.abspath(sys.executable))
    os.environ['PATH'] = dll_path + os.pathsep + os.environ.get('PATH', '')

if __name__ == "__main__":
    main()
