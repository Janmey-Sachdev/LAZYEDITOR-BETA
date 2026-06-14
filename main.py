import os
import sys
import asyncio
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, TextArea, DirectoryTree, Input, Static, RichLog
from textual.events import Key

class WelcomeScreen(Static):
    def compose(self) -> ComposeResult:
        yield Static("⚡ LAZYEDITOR POWER (BETA VERSION)⚡", id="title")
        yield Static("WARNING: This is a beta version. Expect bugs and incomplete features.", id="subtitle")
        yield Static(
            "Shortcuts:\n"
            "• ctrl+b : Toggle File Tree\n"
            "• ctrl+t : Toggle Terminal Pane\n"
            "• ctrl+q : Quit App\n\n"
            "How to Navigate:\n"
            "• Use Tab key to cycle focus between File Tree, Editor, and Terminal Input!", 
            id="shortcuts"
        )

class LazyEditorApp(App):
    CSS = """
    Screen { background: #1a1b26; }
    #main-container { height: 1fr; }
    
    DirectoryTree { 
        width: 30; 
        background: #1f2335; 
        border-right: solid #414868; 
    }
    
    #right-pane { width: 1fr; }
    WelcomeScreen { align: center middle; text-align: center; height: 1fr; background: #1a1b26; }
    
    #title { 
        text-style: bold; 
        color: #7aa2f7; 
        margin-bottom: 1; 
    }
    
    #subtitle { color: #565f89; margin-bottom: 2; }
    #shortcuts { color: #cfc9c2; background: #24283b; padding: 1 2; border: round #414868; }
    TextArea { height: 1fr; background: #1a1b26; }
    
    /* Terminal Container Blocks */
    #terminal-box {
        height: 12;
        border-top: solid #414868;
        background: #16161e;
    }
    RichLog {
        height: 1fr;
        background: #16161e;
        color: #a9b1d6;
    }
    #term-input {
        background: #1f2335;
        color: #7abcfa;
        border: none;
        height: 1;
    }
    
    #command-bar { dock: bottom; background: #1f2335; color: #bb9af7; border: none; }
    """

    BINDINGS = [
        ("ctrl+b", "toggle_sidebar", "Toggle Sidebar"),
        ("ctrl+t", "toggle_terminal", "Toggle Terminal"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self.current_filepath = None
        self.last_known_mtime = None
        self.prompt = "C:\\> " if sys.platform == "win32" else "$ "

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-container"):
            yield DirectoryTree(".", id="file-tree")
            with Vertical(id="right-pane"):
                yield WelcomeScreen(id="welcome")
                yield TextArea(id="editor", show_line_numbers=True)
                
                # Dedicated split container for terminal window + terminal typing input line
                with Vertical(id="terminal-box"):
                    yield RichLog(id="terminal-pane", max_lines=2000, wrap=True)
                    yield Input(placeholder=f"{self.prompt} type terminal command here...", id="term-input")
                
        yield Input(placeholder="Editor Mode: Type :open <path> to browse files...", id="command-bar")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#editor").display = False
        self.query_one("#file-tree").focus()
        
        term = self.query_one("#terminal-pane", RichLog)
        term.write("[bold cyan]Interactive Shell Ready.[/bold cyan] Type inside the lower sub-input line to run scripts.")
        
        self.set_interval(0.5, self.check_external_changes)

    def action_toggle_sidebar(self) -> None:
        tree = self.query_one("#file-tree")
        tree.display = not tree.display

    def action_toggle_terminal(self) -> None:
        box = self.query_one("#terminal-box")
        box.display = not box.display

    @on(DirectoryTree.FileSelected)
    def open_file_from_tree(self, event: DirectoryTree.FileSelected) -> None:
        self.load_file(str(event.path))

    # --- TOP COMMAND BAR HANDLER (FOR EDITOR STUFF) ---
    @on(Input.Submitted, "#command-bar")
    def handle_editor_command(self, event: Input.Submitted) -> None:
        raw_command = event.value.strip()
        cmd_bar = self.query_one("#command-bar", Input)
        
        if not raw_command:
            return
            
        if raw_command.startswith(":open "):
            target_path = raw_command.split(" ", 1)[1]
            full_path = os.path.abspath(os.path.expanduser(target_path))
            if os.path.exists(full_path) and os.path.isfile(full_path):
                self.load_file(full_path)
                cmd_bar.value = ""
            else:
                cmd_bar.value = f"Error: File not found ({target_path})"
                
        elif raw_command.startswith(":cd "):
            target_dir = raw_command.split(" ", 1)[1]
            full_dir = os.path.abspath(os.path.expanduser(target_dir))
            if os.path.exists(full_dir) and os.path.isdir(full_dir):
                self.query_one("#file-tree", DirectoryTree).path = full_dir
                cmd_bar.value = ""
            else:
                cmd_bar.value = f"Error: Directory not found ({target_dir})"
                
        elif raw_command == ":q":
            self.exit()
        else:
            cmd_bar.value = f"Unknown core editor action. Use terminal input box for shell executions."

    # --- BOTTOM TERMINAL INPUT HANDLER (FOR TRUE REAL-TIME SHELL COMMANDS) ---
    @on(Input.Submitted, "#term-input")
    def handle_terminal_input(self, event: Input.Submitted) -> None:
        shell_cmd = event.value.strip()
        term_in = self.query_one("#term-input", Input)
        
        if not shell_cmd:
            return
            
        term_in.value = ""
        self.run_shell_execution(shell_cmd)

    async def run_shell_execution(self, cmd: str) -> None:
        term = self.query_one("#terminal-pane", RichLog)
        term.write(f"\n[bold green]{self.prompt}{cmd}[/bold green]")
        
        try:
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                shell=True
            )
            
            stdout, stderr = await process.communicate()
            
            if stdout:
                term.write(stdout.decode(errors="replace").strip())
            if stderr:
                term.write(f"[bold red]{stderr.decode(errors='replace').strip()}[/bold red]")
                
        except Exception as e:
            term.write(f"[bold red]Shell Execution Error: {e}[/bold red]")

    def load_file(self, path: str) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            
            self.current_filepath = path
            self.last_known_mtime = os.path.getmtime(path)
            
            self.query_one("#welcome").display = False
            editor = self.query_one("#editor", TextArea)
            editor.display = True
            
            editor.load_text(content)
            editor.focus()
            
            self.sub_title = os.path.basename(path)
            self.query_one("#command-bar", Input).placeholder = f"Editing: {path} [Autosave Instantly Enabled]"
        except Exception as e:
            self.notify(f"Could not open file: {e}", severity="error")

    @on(TextArea.Changed, "#editor")
    def handle_keystroke_autosave(self, event: TextArea.Changed) -> None:
        if not self.current_filepath:
            return
        try:
            text_to_save = event.text_area.text
            with open(self.current_filepath, "w", encoding="utf-8") as f:
                f.write(text_to_save)
            self.last_known_mtime = os.path.getmtime(self.current_filepath)
        except Exception:
            pass

    def check_external_changes(self) -> None:
        if not self.current_filepath or not os.path.exists(self.current_filepath):
            return
        try:
            current_mtime = os.path.getmtime(self.current_filepath)
            if self.last_known_mtime and current_mtime > self.last_known_mtime:
                self.last_known_mtime = current_mtime
                editor = self.query_one("#editor", TextArea)
                cursor_location = editor.cursor_location
                with open(self.current_filepath, "r", encoding="utf-8") as f:
                    updated_content = f.read()
                editor.load_text(updated_content)
                editor.cursor_location = cursor_location
        except Exception:
            pass

if __name__ == "__main__":
    app = LazyEditorApp()
    app.run()