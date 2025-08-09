import socket
import threading
import json
import time

HOST = '0.0.0.0'
PORT = 12345

BOARD_SIZE = 15
EMPTY_CELL = ' '

lock = threading.Lock()

players_in_waitlist = []
player_names = {}
game_pairs = {}
game_boards = {}
current_turns = {}
player_symbols = {}
rematch_requests = {}  # {game_id: set([player_socket])}
last_moves = {}        # {game_id: {'row': r, 'col': c}}
rematch_declined_flags = {}  # {game_id: set([player_socket])}

SYMBOL_X = 'X'
SYMBOL_O = 'O'
WIN_CONDITION = 5

def create_new_board():
    return [[EMPTY_CELL for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]

def generate_game_id(socket1, socket2):
    return tuple(sorted([socket1.fileno(), socket2.fileno()]))

def check_win(board, row, col, symbol):
    directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
    for dr, dc in directions:
        count = 1
        for i in range(1, WIN_CONDITION):
            r, c = row + i * dr, col + i * dc
            if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and board[r][c] == symbol:
                count += 1
            else:
                break
        for i in range(1, WIN_CONDITION):
            r, c = row - i * dr, col - i * dc
            if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and board[r][c] == symbol:
                count += 1
            else:
                break
        if count >= WIN_CONDITION:
            return True
    return False

def is_board_full(board):
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if board[r][c] == EMPTY_CELL:
                return False
    return True

def send_to_client(client_socket, message_type, data):
    message = {'type': message_type, 'data': data}
    try:
        client_socket.sendall((json.dumps(message)+ '\n').encode('utf-8'))
    except (socket.error, BrokenPipeError) as e:
        print(f"Lỗi gửi dữ liệu tới client {player_names.get(client_socket, client_socket.getpeername())}: {e}")
        handle_disconnect(client_socket)

def cleanup_game(game_id):
    with lock:
        if game_id in game_boards:
            del game_boards[game_id]
        if game_id in current_turns:
            del current_turns[game_id]
        if game_id in rematch_requests:
            del rematch_requests[game_id]
        if game_id in last_moves:
            del last_moves[game_id]
        if game_id in rematch_declined_flags:
            del rematch_declined_flags[game_id]
        p1_socket, p2_socket = None, None
        for s1, s2 in list(game_pairs.items()):
            if generate_game_id(s1, s2) == game_id:
                p1_socket = s1
                p2_socket = s2
                break
        if p1_socket and p2_socket:
            if p1_socket in game_pairs:
                del game_pairs[p1_socket]
            if p2_socket in game_pairs:
                del game_pairs[p2_socket]
            if p1_socket in player_names and p1_socket not in players_in_waitlist:
                players_in_waitlist.append(p1_socket)
                send_to_client(p1_socket, 'wait', {'message': 'Game kết thúc. Đang chờ đối thủ mới...'})
            if p2_socket in player_names and p2_socket not in players_in_waitlist:
                players_in_waitlist.append(p2_socket)
                send_to_client(p2_socket, 'wait', {'message': 'Game kết thúc. Đang chờ đối thủ mới...'})
        if p1_socket in player_symbols:
            del player_symbols[p1_socket]
        if p2_socket in player_symbols:
            del player_symbols[p2_socket]
        if p1_socket in current_turns:
            del current_turns[p1_socket]
        if p2_socket in current_turns:
            del current_turns[p2_socket]
        print(f"Game {game_id} đã được dọn dẹp.")

def handle_disconnect(client_socket):
    with lock:
        username = player_names.get(client_socket, client_socket.getpeername())
        print(f"Client {username} ({client_socket.getpeername()}) đã ngắt kết nối.")
        if client_socket in players_in_waitlist:
            players_in_waitlist.remove(client_socket)
            print(f"Removed {username} from waitlist.")
        opponent_socket = game_pairs.get(client_socket)
        if opponent_socket:
            game_id = generate_game_id(client_socket, opponent_socket)
            send_to_client(opponent_socket, 'opponent_disconnected', {
                'message': f"Đối thủ {username} đã ngắt kết nối. Trò chơi kết thúc."
            })
            cleanup_game(game_id)
            print(f"Game between {username} and {player_names.get(opponent_socket, 'unknown')} ended due to disconnect.")
        if client_socket in player_names:
            del player_names[client_socket]
        if client_socket in player_symbols:
            del player_symbols[client_socket]
        try:
            client_socket.close()
        except Exception as e:
            print(f"Error closing socket for {username}: {e}")

def handle_client(client_socket, client_address):
    print(f"Đã kết nối tới {client_address}")
    send_to_client(client_socket, 'wait', {'message': 'Chào mừng bạn! Vui lòng nhập tên người dùng để bắt đầu.'})
    try:
        buffer = ""
        while True:
            data = client_socket.recv(4096).decode('utf-8')
            if not data:
                break
            buffer += data
            while '\n' in buffer:
                message_str, buffer = buffer.split('\n', 1)
                if not message_str.strip():
                    continue
                try:
                    message = json.loads(message_str)
                except Exception as e:
                    print(f"Lỗi JSON không hợp lệ từ {client_address}: {e}")
                    continue
                msg_type = message.get('type')
                msg_data = message.get('data')
                current_username = player_names.get(client_socket, client_address)
                print(f"Nhận được từ {current_username}: {msg_type} - {msg_data}")

                if msg_type == 'username_set':
                    username = msg_data['username']
                    with lock:
                        player_names[client_socket] = username
                        if client_socket not in players_in_waitlist and client_socket not in game_pairs:
                            players_in_waitlist.append(client_socket)
                            print(f"Client {client_address} đã đặt tên người dùng là: {username}. Đã thêm vào danh sách chờ.")
                            send_to_client(client_socket, 'wait', {'message': f"Chào mừng {username}! Đang chờ đối thủ..."})
                        else:
                            send_to_client(client_socket, 'wait', {'message': f"Chào mừng {username}! Bạn đang chờ hoặc đã trong game."})
                        if len(players_in_waitlist) >= 2:
                            player1_socket = players_in_waitlist.pop(0)
                            player2_socket = players_in_waitlist.pop(0)
                            if not player_names.get(player1_socket) or not player_names.get(player2_socket):
                                print("Một trong hai người chơi chờ đã ngắt kết nối. Đang tìm người khác.")
                                if player_names.get(player1_socket) and player1_socket not in players_in_waitlist:
                                    players_in_waitlist.insert(0, player1_socket)
                                elif player_names.get(player2_socket) and player2_socket not in players_in_waitlist:
                                    players_in_waitlist.insert(0, player2_socket)
                                continue
                            player1_name = player_names[player1_socket]
                            player2_name = player_names[player2_socket]
                            game_id = generate_game_id(player1_socket, player2_socket)
                            game_boards[game_id] = create_new_board()
                            last_moves[game_id] = None
                            game_pairs[player1_socket] = player2_socket
                            game_pairs[player2_socket] = player1_socket
                            rematch_requests[game_id] = set()
                            rematch_declined_flags[game_id] = set()
                            first_player_socket = player1_socket if time.time() % 2 < 1 else player2_socket
                            current_turns[game_id] = first_player_socket
                            symbol1 = SYMBOL_X if first_player_socket == player1_socket else SYMBOL_O
                            symbol2 = SYMBOL_O if first_player_socket == player1_socket else SYMBOL_X
                            player_symbols[player1_socket] = symbol1
                            player_symbols[player2_socket] = symbol2
                            print(f"Trò chơi bắt đầu giữa {player1_name} ({symbol1}) và {player2_name} ({symbol2}). Game ID: {game_id}")
                            send_to_client(player1_socket, 'game_start', {
                                'symbol': symbol1,
                                'is_turn': (first_player_socket == player1_socket),
                                'board': game_boards[game_id],
                                'opponent_name': player2_name
                            })
                            send_to_client(player2_socket, 'game_start', {
                                'symbol': symbol2,
                                'is_turn': (first_player_socket == player2_socket),
                                'board': game_boards[game_id],
                                'opponent_name': player1_name
                            })

                elif msg_type == 'move':
                    row = msg_data['row']
                    col = msg_data['col']
                    with lock:
                        opponent_socket = game_pairs.get(client_socket)
                        if not opponent_socket:
                            send_to_client(client_socket, 'error', {'message': 'Bạn chưa vào game hoặc game đã kết thúc.'})
                            continue
                        game_id = generate_game_id(client_socket, opponent_socket)
                        if current_turns.get(game_id) != client_socket:
                            send_to_client(client_socket, 'error', {'message': 'Chưa đến lượt của bạn.'})
                            continue
                        board = game_boards.get(game_id)
                        symbol = player_symbols.get(client_socket)
                        if not board or not symbol:
                            send_to_client(client_socket, 'error', {'message': 'Dữ liệu game không hợp lệ.'})
                            continue
                        if 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE and board[row][col] == EMPTY_CELL:
                            board[row][col] = symbol
                            last_moves[game_id] = {'row': row, 'col': col}
                            current_turns[game_id] = opponent_socket
                            send_to_client(client_socket, 'update_board', {'board': board, 'last_move': last_moves[game_id]})
                            send_to_client(opponent_socket, 'update_board', {'board': board, 'last_move': last_moves[game_id]})
                            if check_win(board, row, col, symbol):
                                winner_name = player_names.get(client_socket, client_address[0])
                                loser_name = player_names.get(opponent_socket, opponent_socket.getpeername()[0])
                                print(f"Người chơi {winner_name} ({symbol}) thắng! Game ID: {game_id}")
                                send_to_client(client_socket, 'game_over', {'winner': True, 'message': f"Bạn đã thắng! Chúc mừng, {winner_name}!"})
                                send_to_client(opponent_socket, 'game_over', {'winner': False, 'message': f"Bạn đã thua cuộc! {winner_name} là người thắng."})
                            elif is_board_full(board):
                                print(f"Game hòa! Bàn cờ đã đầy. Game ID: {game_id}")
                                message = "Hòa! Bàn cờ đã đầy."
                                send_to_client(client_socket, 'game_over', {'winner': None, 'message': message})
                                send_to_client(opponent_socket, 'game_over', {'winner': None, 'message': message})
                            else:
                                send_to_client(opponent_socket, 'your_turn', {})
                                send_to_client(client_socket, 'wait_turn', {})
                        else:
                            send_to_client(client_socket, 'error', {'message': 'Ô đã có người hoặc không hợp lệ.'})

                elif msg_type == 'chat':
                    message_content = msg_data['message']
                    sender_name = msg_data.get('sender', 'Người lạ')
                    with lock:
                        opponent_socket = game_pairs.get(client_socket)
                        if opponent_socket:
                            send_to_client(opponent_socket, 'chat', {'message': message_content, 'sender': sender_name})
                            print(f"Chat từ {sender_name} tới {player_names.get(opponent_socket, 'opponent')}: {message_content}")
                        else:
                            print(f"Chat từ {sender_name}: {message_content} (không tìm thấy đối thủ).")
                            send_to_client(client_socket, 'error', {'message': 'Không tìm thấy đối thủ để chat.'})

                # --- Rematch logic ---
                elif msg_type == 'rematch_request':
                    with lock:
                        opponent_socket = game_pairs.get(client_socket)
                        if not opponent_socket:
                            send_to_client(client_socket, 'error', {'message': 'Không tìm thấy đối thủ để đấu lại.'})
                            continue
                        game_id = generate_game_id(client_socket, opponent_socket)
                        if game_id not in rematch_requests:
                            rematch_requests[game_id] = set()
                        rematch_requests[game_id].add(client_socket)
                        send_to_client(opponent_socket, 'rematch_request', {})
                        # If both players requested rematch, start new game
                        if len(rematch_requests[game_id]) == 2:
                            send_to_client(client_socket, 'rematch_start', {})
                            send_to_client(opponent_socket, 'rematch_start', {})
                            game_boards[game_id] = create_new_board()
                            last_moves[game_id] = None
                            first_player_socket = client_socket if time.time() % 2 < 1 else opponent_socket
                            current_turns[game_id] = first_player_socket
                            symbol1 = SYMBOL_X if first_player_socket == client_socket else SYMBOL_O
                            symbol2 = SYMBOL_O if first_player_socket == client_socket else SYMBOL_X
                            player_symbols[client_socket] = symbol1
                            player_symbols[opponent_socket] = symbol2
                            send_to_client(client_socket, 'game_start', {
                                'symbol': symbol1,
                                'is_turn': (first_player_socket == client_socket),
                                'board': game_boards[game_id],
                                'opponent_name': player_names.get(opponent_socket, 'Đối thủ')
                            })
                            send_to_client(opponent_socket, 'game_start', {
                                'symbol': symbol2,
                                'is_turn': (first_player_socket == opponent_socket),
                                'board': game_boards[game_id],
                                'opponent_name': player_names.get(client_socket, 'Đối thủ')
                            })
                            rematch_requests[game_id] = set()  # Reset for next rematch

                elif msg_type == 'rematch_declined':
                    with lock:
                        opponent_socket = game_pairs.get(client_socket)
                        if not opponent_socket:
                            continue
                        game_id = generate_game_id(client_socket, opponent_socket)
                        if game_id not in rematch_declined_flags:
                            rematch_declined_flags[game_id] = set()
                        rematch_declined_flags[game_id].add(client_socket)
                        send_to_client(opponent_socket, 'rematch_declined', {})
                        # If both players declined, cleanup and put both to waitlist
                        if len(rematch_declined_flags[game_id]) == 2:
                            cleanup_game(game_id)

                elif msg_type == 'rematch_start':
                    pass

    except Exception as e:
        print(f"Lỗi trong handle_client cho {client_address}: {e}")
    finally:
        handle_disconnect(client_socket)

def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print(f"Server đang lắng nghe trên {HOST}:{PORT}")
    while True:
        client_socket, client_address = server_socket.accept()
        client_handler = threading.Thread(target=handle_client, args=(client_socket, client_address), daemon=True)
        client_handler.start()

if __name__ == "__main__":
    start_server()