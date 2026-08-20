from sdk.Robot import RPC
import time
import socket
from typing import Optional, Tuple


# Robot TCP portları
ROBOT_XMLRPC_PORT   = 20003   # XML-RPC komut kanalı
ROBOT_REALTIME_PORT = 20004   # Realtime state kanalı


def _tcp_reachable(ip: str, port: int, timeout: float = 2.0) -> bool:
    """
    Belirtilen IP:port TCP bağlantısı kabul ediyor mu?

    RPC() nesnesi oluşturmadan önce port erişilebilirlik testi yapar.
    Robot boot aşamasında port kapalıysa RPC() oluşturmaya gerek yok —
    thread ve soket birikmesi önlenir.

    Returns:
        True  → port açık, bağlantı kabul edildi
        False → port kapalı veya timeout
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        result = s.connect_ex((ip, port))
        s.close()
        return result == 0
    except Exception:
        return False


class RobotConnection:
    def __init__(self, robot_ip: str, verbose: bool = True):
        self.robot_ip = robot_ip
        self.verbose  = verbose
        self.rpc: Optional[RPC] = None

    def connect(self) -> bool:
        """
        Robot bağlantısını kurar.

        Adımlar:
          1) TCP port erişilebilirlik testi (20003 ve 20004)
             → Port kapalıysa RPC() oluşturma — thread/soket birikmesi önlenir
          2) RPC.is_conect class flag sıfırla (True)
             → Önceki timeout'tan False kalmış olabilir
          3) RPC() nesnesi oluştur
          4) Bağlantı doğrula (is_connected)
        """
        # Önce port erişilebilir mi kontrol et
        #
        # DÜZELTİLEN HATA: burada tanımsız bir `verbose` adı okunuyordu —
        # o isim yalnızca modül seviyesindeki connect_robot() fonksiyonunun
        # parametresiydi. Robot portu kapalı olduğu her seferde NameError
        # fırlıyor, hiçbir yerde yakalanmadığı için RobotMonitor thread'i
        # ölüyor ve sipariş "name 'verbose' is not defined" ile düşüyordu.
        # Bayrak artık örneğin kendi alanı.
        if not _tcp_reachable(self.robot_ip, ROBOT_XMLRPC_PORT, timeout=2.0):
            if self.verbose:
                print(f"[connect_robot] ⏳ XML-RPC port {ROBOT_XMLRPC_PORT} kapalı — robot henüz hazır değil.")
            return False

        if not _tcp_reachable(self.robot_ip, ROBOT_REALTIME_PORT, timeout=2.0):
            if self.verbose:
                print(f"[connect_robot] ⏳ Realtime port {ROBOT_REALTIME_PORT} kapalı — robot henüz hazır değil.")
            return False

        # Portlar açık — is_conect flag sıfırla
        try:
            RPC.is_conect = True
        except Exception:
            pass

        # RPC nesnesi oluştur
        try:
            self.rpc = RPC(self.robot_ip)
            connected = self.is_connected()
            if not connected:
                # RPC oluştu ama bağlantı doğrulanamadı — flag sıfırla
                try:
                    RPC.is_conect = True
                except Exception:
                    pass
            return connected
        except Exception as e:
            print(f"[connect_robot] ❌ RPC oluşturma hatası: {e}")
            self.rpc = None
            try:
                RPC.is_conect = True
            except Exception:
                pass
            return False

    def is_connected(self) -> bool:
        """
        Bağlantı doğrulama:
          1) rpc nesnesi var mı?
          2) Realtime soket bağlı mı? (sock_cli_state_state)
          3) XML-RPC ping başarılı mı? (GetControllerIP)
        """
        if self.rpc is None:
            return False
        if not getattr(self.rpc, "sock_cli_state_state", False):
            return False
        try:
            err, ip = self.rpc.GetControllerIP()
            return err == 0 and bool(ip)
        except Exception:
            return False

    def disconnect(self) -> None:
        """Mevcut bağlantıyı temiz şekilde kapatır."""
        if self.rpc is None:
            return
        try:
            if hasattr(self.rpc, "stop_event"):
                self.rpc.stop_event.set()
        except Exception:
            pass
        try:
            sock = getattr(self.rpc, "sock_cli_state", None)
            if sock is not None:
                sock.close()
        except Exception:
            pass
        try:
            if hasattr(self.rpc, "closeRPC_state"):
                self.rpc.closeRPC_state = True
        except Exception:
            pass
        self.rpc = None


def connect_robot(robot_ip: str, retry: int = 3, wait_s: float = 2.0, verbose: bool = True) -> Tuple[Optional[RPC], bool]:
    """
    Yardımcı fonksiyon — robot_manager tarafından çağrılır.

    retry: kaç kez deneneceği
    wait_s: denemeler arası bekleme (s)
    """
    conn = RobotConnection(robot_ip, verbose=verbose)
    for attempt in range(1, retry + 1):
        ok = conn.connect()
        if ok:
            return conn.rpc, True
        if attempt < retry:
            if verbose:
                print(f"[connect_robot] Deneme {attempt}/{retry} başarısız, {wait_s}s bekleniyor...")
            time.sleep(wait_s)
    return None, False
