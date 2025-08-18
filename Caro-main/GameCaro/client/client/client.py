import socket
import threading
import json
import tkinter as tk
from tkinter import messagebox
from datetime import datetime

HOST = '172.20.10.6'
PORT = 12345

BOARD_SIZE = 15
EMPTY_CELL = ' '

THEMES = {
    "light": {
        "BG_COLOR": "#F5F5DC",  
        "BOARD_BG": "#8B4513", 
        "BTN_COLOR": "#D2B48C", 
        "BTN_ACTIVE": "#C19A6B",
        "BTN_TEXT": "#333333",
        "HEADER_BG": "#654321",
        "HEADER_TEXT": "#F5F5DC",
        "CHAT_BG": "#E6D7B7",
        "CHAT_TEXT": "#333333",
        "AVATAR1": "#ffb347",
        "AVATAR2": "#77dd77",
        "LAST_MOVE": "#ffe066",
        "X_COLOR": "#FF0000",   
        "O_COLOR": "#0000FF"
    },
    "dark": {
        "BG_COLOR": "#23272f",
        "BOARD_BG": "#5C4033",
        "BTN_COLOR": "#4a5d71",
        "BTN_ACTIVE": "#64778c",
        "BTN_TEXT": "#ffffff",
        "HEADER_BG": "#1a1d23",
        "HEADER_TEXT": "#f0f4f8",
        "CHAT_BG": "#23272f",
        "CHAT_TEXT": "#f0f4f8",
        "AVATAR1": "#ffb347",
        "AVATAR2": "#77dd77",
        "LAST_MOVE": "#ffe066",
        "X_COLOR": "#ff4d4d",
        "O_COLOR": "#4d4dff"
    }
}

class CaroGameClient:
    def __init__(self, master):
        self.theme = "light"
        self.colors = THEMES[self.theme]
        self.master = master
        master.title("Caro Game Online")
        master.geometry("1000x950")
        master.resizable(False, False)
        master.configure(bg=self.colors["BG_COLOR"])
        self.username = ""
        self.opponent_name = ""
        self.is_connected = False
        self.my_symbol = ''
        self.is_my_turn = False
        self.game_board = [[EMPTY_CELL for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        self.buttons = []
        self.client_socket = None
        self.receive_buffer = ""
        self.rematch_requested = False
        self.opponent_rematch = False
        self.stats = {"win": 0, "loss": 0, "draw": 0}
        self.sound_enabled = True
        self.last_move = None
        self.wait_frame = None
        self.game_frame = None
        self.rematch_declined = False
        self.create_wait_screen()
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_wait_screen(self):
        self.wait_frame = tk.Frame(self.master, bg=self.colors["BG_COLOR"])
        self.wait_frame.pack(fill=tk.BOTH, expand=True)

        title = tk.Label(self.wait_frame, text="Caro Game Online", font=("Arial", 32, "bold"),
                         bg=self.colors["BG_COLOR"], fg=self.colors["HEADER_BG"], pady=40)
        title.pack()

        start_btn = tk.Button(self.wait_frame, text="Bắt đầu", font=("Arial", 18, "bold"),
                             bg=self.colors["BTN_COLOR"], fg=self.colors["BTN_TEXT"],
                             activebackground=self.colors["BTN_ACTIVE"], width=20, height=2,
                             command=self.start_game)
        start_btn.pack(pady=20)

        info_btn = tk.Button(self.wait_frame, text="Thông tin trò chơi", font=("Arial", 18, "bold"),
                             bg=self.colors["BTN_COLOR"], fg=self.colors["BTN_TEXT"],
                             activebackground=self.colors["BTN_ACTIVE"], width=20, height=2,
                             command=self.show_game_info)
        info_btn.pack(pady=20)

        exit_btn = tk.Button(self.wait_frame, text="Thoát", font=("Arial", 18, "bold"),
                             bg=self.colors["BTN_COLOR"], fg=self.colors["BTN_TEXT"],
                             activebackground=self.colors["BTN_ACTIVE"], width=20, height=2,
                             command=self.on_closing)
        exit_btn.pack(pady=20)

    def start_game(self):
        self.wait_frame.destroy()
        self.create_widgets()

    def show_game_info(self):
        info_text = (
            "Hướng dẫn chơi Caro:\n\n"
            "- Hai người chơi lần lượt đánh dấu X và O lên bàn cờ 15x15.\n"
            "- Người chơi nào có 5 ký hiệu liên tiếp (ngang, dọc, chéo) sẽ thắng.\n"
            "- Nếu bàn cờ đầy mà không ai thắng thì hòa.\n"
            "- Có thể chat với đối thủ trong khi chơi.\n"
            "- Sau khi kết thúc, có thể chọn đấu lại hoặc thoát."
        )
        messagebox.showinfo("Thông tin trò chơi", info_text)

    def on_closing(self):
        self.disconnect_from_server()
        self.master.destroy()

    def disconnect_from_server(self):
        if self.is_connected and self.client_socket:
            try:
                self.is_connected = False
                self.client_socket.shutdown(socket.SHUT_RDWR)
            except Exception as e:
                print(f"Error shutting down socket: {e}")
            try:
                self.client_socket.close()
            except Exception as e:
                print(f"Error closing socket: {e}")
            self.client_socket = None

    def create_widgets(self):
        self.header_frame = tk.Frame(self.master, bg=self.colors["HEADER_BG"])
        self.header_frame.pack(side=tk.TOP, fill=tk.X)
        self.header_label = tk.Label(self.header_frame, text="Caro Game Online", font=("Arial", 28, "bold"),
                                     bg=self.colors["HEADER_BG"], fg=self.colors["HEADER_TEXT"], pady=16)
        self.header_label.pack()

        self.top_section_frame = tk.Frame(self.master, bd=2, relief=tk.GROOVE, bg=self.colors["BG_COLOR"])
        self.top_section_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

        self.username_frame = tk.Frame(self.top_section_frame, bg=self.colors["BG_COLOR"])
        self.username_frame.pack(side=tk.LEFT, padx=5, pady=5)
        self.username_label = tk.Label(self.username_frame, text="Nhập tên của bạn:", font=("Arial", 12), bg=self.colors["BG_COLOR"])
        self.username_label.pack(side=tk.LEFT, padx=5, pady=5)
        self.username_entry = tk.Entry(self.username_frame, width=20, font=("Arial", 12))
        self.username_entry.pack(side=tk.LEFT, padx=5, pady=5)
        self.username_entry.bind("<Return>", self.set_username)
        self.set_username_button = tk.Button(self.username_frame, text="Xác nhận", command=self.set_username,
                                             bg=self.colors["BTN_COLOR"], fg=self.colors["BTN_TEXT"],
                                             activebackground=self.colors["BTN_ACTIVE"], font=("Arial", 12))
        self.set_username_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.avatar_frame = tk.Frame(self.top_section_frame, bg=self.colors["BG_COLOR"])
        self.avatar_frame.pack(side=tk.LEFT, padx=20)
        self.avatar1 = tk.Canvas(self.avatar_frame, width=40, height=40, bg=self.colors["BG_COLOR"], highlightthickness=0)
        self.avatar1.create_oval(5, 5, 35, 35, fill=self.colors["AVATAR1"], outline="")
        self.avatar1.pack(side=tk.LEFT)
        self.avatar_label1 = tk.Label(self.avatar_frame, text="Bạn", font=("Arial", 12), bg=self.colors["BG_COLOR"])
        self.avatar_label1.pack(side=tk.LEFT, padx=5)
        self.avatar2 = tk.Canvas(self.avatar_frame, width=40, height=40, bg=self.colors["BG_COLOR"], highlightthickness=0)
        self.avatar2.create_oval(5, 5, 35, 35, fill=self.colors["AVATAR2"], outline="")
        self.avatar2.pack(side=tk.LEFT, padx=20)
        self.avatar_label2 = tk.Label(self.avatar_frame, text="Đối thủ", font=("Arial", 12), bg=self.colors["BG_COLOR"])
        self.avatar_label2.pack(side=tk.LEFT, padx=5)

        self.stats_frame = tk.Frame(self.top_section_frame, bg=self.colors["BG_COLOR"])
        self.stats_frame.pack(side=tk.LEFT, padx=20)
        self.stats_label = tk.Label(self.stats_frame, text="Thắng: 0  Thua: 0  Hòa: 0", font=("Arial", 12), bg=self.colors["BG_COLOR"])
        self.stats_label.pack()

        self.control_frame = tk.Frame(self.top_section_frame, bg=self.colors["BG_COLOR"])
        self.control_frame.pack(side=tk.RIGHT, padx=5)
        self.theme_button = tk.Button(self.control_frame, text="Chuyển", command=self.toggle_theme,
                                      bg=self.colors["BTN_COLOR"], fg=self.colors["BTN_TEXT"], font=("Arial", 10))
        self.theme_button.pack(side=tk.LEFT, padx=5)
        self.sound_button = tk.Button(self.control_frame, text="Tắt âm", command=self.toggle_sound,
                                      bg=self.colors["BTN_COLOR"], fg=self.colors["BTN_TEXT"], font=("Arial", 10))
        self.sound_button.pack(side=tk.LEFT, padx=5)
        self.clear_chat_button = tk.Button(self.control_frame, text="Xóa chat", command=self.clear_chat,
                                           bg=self.colors["BTN_COLOR"], fg=self.colors["BTN_TEXT"], font=("Arial", 10))
        self.clear_chat_button.pack(side=tk.LEFT, padx=5)

        self.info_frame = tk.Frame(self.master, bd=2, relief=tk.GROOVE, bg=self.colors["BG_COLOR"])
        self.info_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        self.status_label = tk.Label(self.info_frame, text="Đang chờ kết nối...", font=("Arial", 14, "bold"), bg=self.colors["BG_COLOR"])
        self.status_label.pack(side=tk.LEFT, padx=10, pady=5)
        self.symbol_label = tk.Label(self.info_frame, text="Ký hiệu của bạn: ", font=("Arial", 12), bg=self.colors["BG_COLOR"])
        self.symbol_label.pack(side=tk.LEFT, padx=10, pady=5)
        self.opponent_label = tk.Label(self.info_frame, text="Đối thủ: ", font=("Arial", 12), bg=self.colors["BG_COLOR"])
        self.opponent_label.pack(side=tk.LEFT, padx=10, pady=5)

        self.board_frame = tk.Frame(self.master, bd=2, relief=tk.SUNKEN, bg=self.colors["BOARD_BG"])
        self.board_frame.pack(side=tk.TOP, padx=10, pady=5, expand=True)
        self.buttons = []
        for r in range(BOARD_SIZE): 
            row_buttons = []
            for c in range(BOARD_SIZE):
                button = tk.Button(self.board_frame, text=EMPTY_CELL, width=3, height=1,
                                   font=("Arial", 12, "bold"),
                                   command=lambda r=r, c=c: self.make_move(r, c),
                                   state=tk.DISABLED,
                                   bg=self.colors["BTN_COLOR"], fg=self.colors["BTN_TEXT"],
                                   activebackground=self.colors["BTN_ACTIVE"])
                button.grid(row=r, column=c, padx=1, pady=1)
                button.bind("<Enter>", lambda e, b=button: b.config(bg=self.colors["BTN_ACTIVE"]))
                button.bind("<Leave>", lambda e, b=button: b.config(bg=self.colors["BTN_COLOR"]))
                row_buttons.append(button)
            self.buttons.append(row_buttons)

        self.chat_history_frame = tk.Frame(self.master, bd=2, relief=tk.GROOVE, bg=self.colors["BG_COLOR"])
        self.chat_history_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        self.chat_history = tk.Text(self.chat_history_frame, height=7, width=90, state=tk.DISABLED,
                                    font=("Arial", 12), bg=self.colors["CHAT_BG"], fg=self.colors["CHAT_TEXT"])
        self.chat_history.pack(padx=5, pady=5)
        self.chat_frame = tk.Frame(self.master, bd=2, relief=tk.GROOVE, bg=self.colors["BG_COLOR"])
        self.chat_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)

        self.chat_entry = tk.Entry(self.chat_frame, width=70, font=("Arial", 12))
        self.chat_entry.pack(side=tk.LEFT, padx=5, pady=5)
        self.chat_entry.bind("<Return>", self.send_chat_message)
        self.send_button = tk.Button(self.chat_frame, text="Gửi", command=self.send_chat_message,
                                     bg=self.colors["BTN_COLOR"], fg=self.colors["BTN_TEXT"], font=("Arial", 12))
        self.send_button.pack(side=tk.LEFT, padx=5, pady=5)
        self.chat_entry.config(state=tk.DISABLED)
        self.send_button.config(state=tk.DISABLED)

        self.footer_frame = tk.Frame(self.master, bg=self.colors["HEADER_BG"])
        self.footer_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.footer_label = tk.Label(self.footer_frame, text="© 2024 Caro Game | Powered by GitHub Copilot",
                                     font=("Arial", 10), bg=self.colors["HEADER_BG"], fg=self.colors["HEADER_TEXT"], pady=5)
        self.footer_label.pack()

    def set_username(self, event=None):
        name = self.username_entry.get().strip()
        if name:
            self.username = name
            self.username_label.config(text=f"Xin chào, {self.username}!")
            self.username_entry.config(state=tk.DISABLED)
            self.set_username_button.config(state=tk.DISABLED)
            self.connect_to_server()
            self.status_label.config(text="Đang kết nối đến server...")
            self.symbol_label.config(text="Ký hiệu của bạn: ")
            self.opponent_label.config(text="Đối thủ: ")
            self.chat_history.config(state=tk.NORMAL)
            self.chat_history.delete(1.0, tk.END)
            self.chat_history.config(state=tk.DISABLED)
        else:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập tên người chơi.")

    def connect_to_server(self):
        self.status_label.config(text="Đang kết nối...")
        self.disconnect_from_server()
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.is_connected = False
        self.receive_buffer = ""
        try:
            self.client_socket.connect((HOST, PORT))
            self.is_connected = True
            self.send_to_server('username_set', {'username': self.username})
            self.status_label.config(text="Đã kết nối, chờ đối thủ...")
            threading.Thread(target=self.listen_from_server, daemon=True).start()
            self.chat_entry.config(state=tk.NORMAL)
            self.send_button.config(state=tk.NORMAL)
        except ConnectionRefusedError:
            messagebox.showerror("Lỗi", "Không thể kết nối đến server. Đảm bảo server đang chạy.")
            self.master.destroy()
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi kết nối: {e}")
            self.master.destroy()

    def process_server_message(self, message):
        msg_type = message.get('type')
        msg_data = message.get('data')
        if msg_type == 'game_start':
            self.my_symbol = msg_data['symbol']
            self.is_my_turn = msg_data['is_turn']
            self.game_board = msg_data['board']
            self.opponent_name = msg_data.get('opponent_name', 'Đối thủ')
            self.symbol_label.config(text=f"Ký hiệu của bạn: {self.my_symbol}")
            self.opponent_label.config(text=f"Đối thủ: {self.opponent_name}")
            self.last_move = None
            self.update_board_gui()
            self.update_turn_highlight()
            if self.is_my_turn:
                self.status_label.config(text="Đến lượt của bạn!")
                self.enable_board_buttons()
            else:
                self.status_label.config(text="Chờ đối thủ đi...")
                self.disable_board_buttons()
            messagebox.showinfo("Game Start", f"Trò chơi bắt đầu! Bạn là '{self.my_symbol}'. Đối thủ của bạn là {self.opponent_name}.")
        elif msg_type == 'update_board':
            self.game_board = msg_data['board']
            self.last_move = msg_data.get('last_move')
            self.update_board_gui()
        elif msg_type == 'your_turn':
            self.is_my_turn = True
            self.status_label.config(text="Đến lượt của bạn!")
            self.update_turn_highlight()
            self.enable_board_buttons()
        elif msg_type == 'wait_turn':
            self.is_my_turn = False
            self.status_label.config(text="Chờ đối thủ đi...")
            self.update_turn_highlight()
            self.disable_board_buttons()
        elif msg_type == 'game_over':
            winner_info = msg_data['winner']
            message = msg_data['message']
            self.status_label.config(text="Trò chơi kết thúc.")
            self.disable_board_buttons()
            self.update_stats(winner_info)
            messagebox.showinfo("Kết thúc game", message)
            self.ask_rematch()
        elif msg_type == 'error':
            messagebox.showerror("Lỗi", msg_data['message'])
            self.status_label.config(text="Lỗi: " + msg_data['message'])
        elif msg_type == 'wait':
            self.status_label.config(text=msg_data['message'])
        elif msg_type == 'opponent_disconnected':
            messagebox.showinfo("Đối thủ ngắt kết nối", msg_data['message'])
            self.status_label.config(text="Đối thủ đã ngắt kết nối. Trò chơi kết thúc.")
            self.opponent_label.config(text="Đối thủ: ")
            self.reset_game_state()
        elif msg_type == 'chat':
            sender = msg_data.get('sender', 'Đối thủ')
            chat_message = msg_data['message']
            self.append_chat_message(f"{sender}: {chat_message}")
        elif msg_type == 'rematch_request':
            self.opponent_rematch = True
            if self.rematch_requested:
                self.start_rematch()
            else:
                self.status_label.config(text="Đối thủ muốn đấu lại! Bạn có muốn đấu lại không?")
                self.ask_rematch(opponent_requested=True)
        elif msg_type == 'rematch_start':
            self.start_rematch()
        elif msg_type == 'rematch_declined':
            self.status_label.config(text="Đối thủ đã từ chối đấu lại. Đang chờ đối thủ mới...")
            self.reset_game_state()
            self.wait_for_new_opponent()

    def ask_rematch(self, opponent_requested=False):
        if opponent_requested:
            question = "Đối thủ muốn đấu lại. Bạn có muốn đấu lại không?"
        else:
            question = "Bạn có muốn đấu lại không?"
        result = messagebox.askyesno("Đấu lại", question)
        if result:
            self.rematch_requested = True
            self.rematch_declined = False
            self.send_to_server('rematch_request', {})
            if self.opponent_rematch:
                self.start_rematch()
            else:
                self.status_label.config(text="Đang chờ đối thủ đồng ý đấu lại...")
        else:
            self.rematch_requested = False
            self.opponent_rematch = False
            self.rematch_declined = True
            self.status_label.config(text="Bạn đã từ chối đấu lại.")
            self.send_to_server('rematch_declined', {})
            self.reset_game_state()
            self.wait_for_new_opponent()

    def wait_for_new_opponent(self):
        self.disable_board_buttons()
        self.chat_entry.config(state=tk.DISABLED)
        self.send_button.config(state=tk.DISABLED)
        self.status_label.config(text="Đang chờ đối thủ mới...")

    def start_rematch(self):
        self.rematch_requested = False
        self.opponent_rematch = False
        self.send_to_server('rematch_start', {})
        self.reset_game_state()
        self.status_label.config(text="Đã bắt đầu trận đấu lại! Chờ đối thủ...")

    def send_chat_message(self, event=None):
        message = self.chat_entry.get().strip()
        if message:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.send_to_server('chat', {'message': message, 'sender': self.username})
            self.append_chat_message(f"[{timestamp}] Bạn ({self.username}): {message}")
            self.chat_entry.delete(0, tk.END)

    def append_chat_message(self, message):
        self.chat_history.config(state=tk.NORMAL)
        self.chat_history.insert(tk.END, message + "\n")
        self.chat_history.see(tk.END)
        self.chat_history.config(state=tk.DISABLED)

    def clear_chat(self):
        self.chat_history.config(state=tk.NORMAL)
        self.chat_history.delete(1.0, tk.END)
        self.chat_history.config(state=tk.DISABLED)

    def toggle_theme(self):
        self.theme = "dark" if self.theme == "light" else "light"
        self.colors = THEMES[self.theme]
        self.master.configure(bg=self.colors["BG_COLOR"])
        self.header_frame.config(bg=self.colors["HEADER_BG"])
        self.header_label.config(bg=self.colors["HEADER_BG"], fg=self.colors["HEADER_TEXT"])
        self.top_section_frame.config(bg=self.colors["BG_COLOR"])
        self.username_frame.config(bg=self.colors["BG_COLOR"])
        self.avatar_frame.config(bg=self.colors["BG_COLOR"])
        self.avatar1.config(bg=self.colors["BG_COLOR"])
        self.avatar2.config(bg=self.colors["BG_COLOR"])
        self.avatar_label1.config(bg=self.colors["BG_COLOR"])
        self.avatar_label2.config(bg=self.colors["BG_COLOR"])
        self.stats_frame.config(bg=self.colors["BG_COLOR"])
        self.stats_label.config(bg=self.colors["BG_COLOR"])
        self.control_frame.config(bg=self.colors["BG_COLOR"])
        self.theme_button.config(bg=self.colors["BTN_COLOR"], fg=self.colors["BTN_TEXT"])
        self.sound_button.config(bg=self.colors["BTN_COLOR"], fg=self.colors["BTN_TEXT"])
        self.clear_chat_button.config(bg=self.colors["BTN_COLOR"], fg=self.colors["BTN_TEXT"])
        self.info_frame.config(bg=self.colors["BG_COLOR"])
        self.status_label.config(bg=self.colors["BG_COLOR"])
        self.symbol_label.config(bg=self.colors["BG_COLOR"])
        self.opponent_label.config(bg=self.colors["BG_COLOR"])
        self.board_frame.config(bg=self.colors["BOARD_BG"])
        self.chat_history_frame.config(bg=self.colors["BG_COLOR"])
        self.chat_history.config(bg=self.colors["CHAT_BG"], fg=self.colors["CHAT_TEXT"])
        self.chat_frame.config(bg=self.colors["BG_COLOR"])
        self.footer_frame.config(bg=self.colors["HEADER_BG"])
        self.footer_label.config(bg=self.colors["HEADER_BG"], fg=self.colors["HEADER_TEXT"])
        self.update_board_gui()

    def toggle_sound(self):
        self.sound_enabled = not self.sound_enabled
        self.sound_button.config(text="Bật âm" if not self.sound_enabled else "Tắt âm")

    def update_board_gui(self):
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                btn = self.buttons[r][c]
                symbol = self.game_board[r][c]
            
                # Cập nhật văn bản của nút
                btn.config(text=symbol)
            
                # Đặt màu chữ dựa trên ký hiệu và CẬP NHẬT THÊM disabledforeground
                if symbol == 'X':
                    btn.config(fg=self.colors["X_COLOR"], disabledforeground=self.colors["X_COLOR"])
                elif symbol == 'O':
                    btn.config(fg=self.colors["O_COLOR"], disabledforeground=self.colors["O_COLOR"])
                else:
                    # Đặt lại màu chữ mặc định cho ô trống
                    btn.config(fg=self.colors["BTN_TEXT"], disabledforeground=self.colors["BTN_TEXT"])

                # Logic tô màu nền cho các ô
                is_last_move = self.last_move and (r, c) == (self.last_move.get('row'), self.last_move.get('col'))
            
                if is_last_move:
                    btn.config(bg=self.colors["LAST_MOVE"])
                elif symbol != EMPTY_CELL:
                    btn.config(bg=self.colors["BTN_ACTIVE"])
                else:
                    btn.config(bg=self.colors["BTN_COLOR"])
                
                # Cập nhật lại sự kiện hover để sử dụng màu nền mới
                btn.bind("<Enter>", lambda e, b=btn: b.config(bg=self.colors["BTN_ACTIVE"]))
                btn.bind("<Leave>", lambda e, b=btn: b.config(bg=self.colors["BTN_COLOR"]))

    def enable_board_buttons(self):
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if self.game_board[r][c] == EMPTY_CELL:
                    self.buttons[r][c].config(state=tk.NORMAL)

    def disable_board_buttons(self):
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                self.buttons[r][c].config(state=tk.DISABLED)

    def update_turn_highlight(self):
        if self.is_my_turn:
            self.avatar_label1.config(font=("Arial", 12, "bold"))
            self.avatar_label2.config(font=("Arial", 12))
        else:
            self.avatar_label1.config(font=("Arial", 12))
            self.avatar_label2.config(font=("Arial", 12, "bold"))

    def update_stats(self, winner_info):
        if winner_info is True:
            self.stats["win"] += 1
        elif winner_info is False:
            self.stats["loss"] += 1
        else:
            self.stats["draw"] += 1
        self.stats_label.config(text=f"Thắng: {self.stats['win']}  Thua: {self.stats['loss']}  Hòa: {self.stats['draw']}")

    def make_move(self, row, col):
        if self.is_my_turn and self.game_board[row][col] == EMPTY_CELL:
            move_data = {'row': row, 'col': col}
            self.last_move = {'row': row, 'col': col}
            self.send_to_server('move', move_data)
            self.disable_board_buttons()
            self.status_label.config(text="Chờ đối thủ đi...")
            
        else:
            if not self.is_my_turn:
                messagebox.showwarning("Lượt đi", "Chưa đến lượt của bạn.")
            else:
                messagebox.showwarning("Ô đã chọn", "Ô này không hợp lệ.")

    def send_to_server(self, message_type, data):
        message = {'type': message_type, 'data': data}
        try:
            self.client_socket.sendall((json.dumps(message) + '\n').encode('utf-8'))
        except (socket.error, BrokenPipeError) as e:
            print(f"Error sending to server: {e}")
            self.is_connected = False
            self.master.after(0, lambda: messagebox.showerror("Lỗi", "Mất kết nối với server."))
            self.master.after(0, self.master.destroy)

    def listen_from_server(self):
        while self.is_connected:
            try:
                data = self.client_socket.recv(4096).decode('utf-8')
                if not data:
                    print("Server đã đóng kết nối.")
                    self.is_connected = False
                    self.master.after(0, lambda: messagebox.showerror("Lỗi", "Mất kết nối với server."))
                    self.master.after(0, self.master.destroy)
                    break
                self.receive_buffer += data
                while '\n' in self.receive_buffer:
                    message_str, self.receive_buffer = self.receive_buffer.split('\n', 1)
                    if message_str:
                        try:
                            message = json.loads(message_str)
                            self.master.after(0, self.process_server_message, message)
                        except json.JSONDecodeError as e:
                            print(f"Lỗi phân tích JSON: {e} - Dữ liệu: '{message_str}'")
                            continue
            except (socket.error, ConnectionResetError, BrokenPipeError) as e:
                print(f"Lỗi nhận dữ liệu từ server: {e}")
                self.is_connected = False
                self.master.after(0, lambda: messagebox.showerror("Lỗi", "Mất kết nối với server."))
                self.master.after(0, self.master.destroy)
                break
            except Exception as e:
                print(f"Lỗi không mong muốn trong listen_from_server: {e}")
                self.is_connected = False
                self.master.after(0, lambda: messagebox.showerror("Lỗi", f"Lỗi không xác định: {e}"))
                self.master.after(0, self.master.destroy)
                break

    def reset_game_state(self):
        self.my_symbol = ''
        self.is_my_turn = False
        self.game_board = [[EMPTY_CELL for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        self.last_move = None
        self.update_board_gui()
        self.disable_board_buttons()
        self.status_label.config(text="Sẵn sàng cho game mới. Đang chờ đối thủ...")
        self.symbol_label.config(text="Ký hiệu của bạn: ")
        self.opponent_name = ""
        self.opponent_label.config(text="Đối thủ: ")
        self.chat_history.config(state=tk.NORMAL)
        self.chat_history.delete(1.0, tk.END)
        self.chat_history.config(state=tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk()
    game_client = CaroGameClient(root)
    root.mainloop()