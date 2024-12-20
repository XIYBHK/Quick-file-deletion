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
import errno
import stat
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
        # 检查是否为SVN目录
        if ".svn" in path:
            logger.info(f"检测到SVN目录: {path}")
            if force:
                # 使用系统命令强制删除
                if os.name == 'nt':  # Windows系统
                    os.system(f'rmdir /s /q "{path}"')
                else:  # Unix/Linux系统
                    os.system(f'rm -rf "{path}"')
                if verbose:
                    logger.info(f"已强制删除SVN目录: {path}")
                return add_to_history(os.path.basename(path), "SVN目录")
            else:
                logger.warning(f"跳过SVN目录: {path}")
                return None

        if os.path.isfile(path):
            try:
                os.chmod(path, 0o777)  # 尝试修改文件权限
                os.remove(path)
                if verbose:
                    logger.info(f"文件 {path} 已删除")
                return add_to_history(os.path.basename(path), "文件")
            except PermissionError:
                if force and os.name == 'nt':
                    # Windows下使用del命令强制删除
                    os.system(f'del /f /q "{path}"')
                    if verbose:
                        logger.info(f"已强制删除文件: {path}")
                    return add_to_history(os.path.basename(path), "文件")
                raise

        elif os.path.isdir(path):
            file_list = []
            if recursive:
                try:
                    # 先尝试更改目录权限
                    for root, dirs, files in os.walk(path, topdown=True):
                        for name in files + dirs:
                            try:
                                full_path = os.path.join(root, name)
                                os.chmod(full_path, 0o777)
                            except:
                                pass
                        file_list.extend(files)
                    
                    shutil.rmtree(path, onerror=handle_remove_readonly)
                except Exception as e:
                    if force and os.name == 'nt':
                        # Windows下使用rd命令强制删除
                        os.system(f'rd /s /q "{path}"')
                    else:
                        raise e
                
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
        raise

def handle_remove_readonly(func, path, exc):
    """处理只读文件的删除"""
    excvalue = exc[1]
    if func in (os.rmdir, os.remove, os.unlink) and excvalue.errno == errno.EACCES:
        # 尝试更改文件/目录权限
        os.chmod(path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
        func(path)  # 重试删除
    else:
        raise

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
        self.pending_deletions = []  # 添加待删除队列
        self.force_delete = tk.BooleanVar(value=True)
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
        
        # 添加强制删除选项
        force_frame = tk.Frame(warning_frame, bg="red")
        force_frame.pack(pady=(5,0))
        tk.Checkbutton(force_frame, text="强制删除（处理只读文件和特殊目录）", 
                      variable=self.force_delete, bg="red", fg="white",
                      selectcolor="darkred", font=("Arial", 10)).pack()

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

        # 添加右键菜单
        self.context_menu = tk.Menu(self.master, tearoff=0)
        self.context_menu.add_command(label="复制路径", command=self.copy_path)
        self.context_menu.add_command(label="删除记录", command=self.delete_history_entry)
        self.history_tree.bind("<Button-3>", self.show_context_menu)

    def show_context_menu(self, event):
        try:
            item = self.history_tree.identify_row(event.y)
            if item:
                self.history_tree.selection_set(item)
                self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def copy_path(self):
        selected = self.history_tree.selection()
        if selected:
            item = selected[0]
            path = self.history_tree.item(item)['values'][2]  # 获取文件/目录名
            self.master.clipboard_clear()
            self.master.clipboard_append(path)

    def delete_history_entry(self):
        selected = self.history_tree.selection()
        if selected and messagebox.askyesno("确认", "是否删除选中的历史记录？"):
            for item in selected:
                self.history_tree.delete(item)
            self._save_current_history()

    def _save_current_history(self):
        """保存当前显示的历史记录到文件"""
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                for item in self.history_tree.get_children():
                    values = self.history_tree.item(item)['values']
                    f.write(f"{values[0]}|{values[1]}|{values[2]}\n")
        except Exception as e:
            logger.error(f"保存历史记录时出错: {e}")

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
        self.pending_deletions = paths
        total = len(paths)
        deleted = 0
        
        # 创建进度条窗口
        progress_window = tk.Toplevel(self.master)
        progress_window.title("删除进度")
        progress = ttk.Progressbar(progress_window, length=300, mode='determinate')
        progress.pack(padx=10, pady=10)
        label = tk.Label(progress_window, text="正在删除...")
        label.pack(pady=5)
        
        for path in paths:
            if not self.pending_deletions:  # 允许用户取消
                break
                
            try:
                progress['value'] = (deleted / total) * 100
                label.config(text=f"正在删除: {shorten_path(path)}")
                progress_window.update()
                
                history_entry = await self._delete_file_or_directory_async(path)
                if history_entry:
                    self.update_history(history_entry)
                    deleted += 1
                else:
                    logger.warning(f"跳过删除 {path}")
                    
            except PermissionError as pe:
                if self.force_delete.get():
                    try:
                        # 尝试强制删除
                        history_entry = await self._delete_file_or_directory_async(path, force=True)
                        if history_entry:
                            self.update_history(history_entry)
                            deleted += 1
                        else:
                            logger.error(f"强制删除失败: {path}")
                            messagebox.showerror("错误", f"无法强制删除 {shorten_path(path)}")
                    except Exception as e:
                        logger.error(f"强制删除时出错: {e}")
                        messagebox.showerror("错误", f"强制删除失败 {shorten_path(path)}: {str(e)}")
                else:
                    logger.error(f"权限错误: {pe}")
                    messagebox.showerror("权限错误", 
                        f"无法删除 {shorten_path(path)}\n"
                        "原因：需要管理员权限或文件正在被使用\n"
                        "建议：尝试勾选'强制删除'选项")
            except Exception as e:
                logger.error(f"删除错误: {e}")
                messagebox.showerror("错误", f"删除 {shorten_path(path)} 时发生错误: {str(e)}")
                
        progress_window.destroy()
        self.pending_deletions.clear()
        
        if deleted == total:
            messagebox.showinfo("完成", f"成功删除了 {deleted} 个文件/目录")
        else:
            messagebox.showwarning("部分完成", f"共 {total} 个项目中，成功删除了 {deleted} 个")

    # 3. 异步删除文件或目录
    async def _delete_file_or_directory_async(self, path: str, force: bool = True) -> Optional[str]:
        # 这里使用 asyncio 来异步执行删除操作
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, delete_file_or_directory, path, force)

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
    try:
        dll_path = os.path.dirname(os.path.abspath(sys.executable))
        os.environ['PATH'] = dll_path + os.pathsep + os.environ.get('PATH', '')
        
        # 检查必要的文件权限
        log_dir = os.path.dirname(log_file)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        # 验证日志文件和历史文件的写入权限
        with open(log_file, 'a'): pass
        with open(HISTORY_FILE, 'a'): pass
            
    except Exception as e:
        messagebox.showerror("初始化错误", 
                           f"程序初始化失败: {str(e)}\n"
                           "请确保程序有足够的文件访问权限。")
        sys.exit(1)

if __name__ == "__main__":
    main()
