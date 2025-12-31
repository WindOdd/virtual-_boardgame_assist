import socket
import json

# 設定目標 (廣播)
BROADCAST_IP = "255.255.255.255"
PORT = 37020
MAGIC_STRING = "DISCOVER_AKKA_SERVER"

# 建立 UDP Socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

# 設定超時 (避免卡住)
sock.settimeout(3.0)

try:
    print(f"📡 發送廣播到 {BROADCAST_IP}:{PORT} ...")
    sock.sendto(MAGIC_STRING.encode(), (BROADCAST_IP, PORT))

    print("⏳ 等待 Server 回應...")
    data, addr = sock.recvfrom(1024)
    
    print(f"\n🎉 收到來自 {addr} 的回應！")
    print(f"📦 內容: {data.decode()}")
    
    # 嘗試解析 JSON
    info = json.loads(data.decode())
    #print(f"✅ Server IP: {info.get('ip')}")
    #print(f"✅ API Port: {info.get('port')}")

except socket.timeout:
    print("❌ 等待逾時：Server 有收到 (看 Jetson Log)，但 RPi 沒收到回信。")
    print("   可能原因：RPi 的防火牆擋住了 UDP 回傳封包。")
except Exception as e:
    print(f"❌ 錯誤: {e}")
finally:
    sock.close()