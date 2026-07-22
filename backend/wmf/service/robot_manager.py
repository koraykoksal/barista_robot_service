"""
robot_manager.py

─────────────────────────────────────────────────────────────────
SDK (Robot.py) GERÇEK DAVRANIŞI — DOĞRULANMIŞ
─────────────────────────────────────────────────────────────────

1) YAZMA — SetDO(id, status)
   • status=1  → TRUE  (HIGH)
   • status=0  → FALSE (LOW)
   • return: hata kodu (0 = başarı)

2) DO OKUMA — GetDO()
   • return: (0, [cl_dgt_output_h, cl_dgt_output_l])
   • cl_dgt_output_l  → DO0..DO7   (bit0..bit7)
   • cl_dgt_output_h  → DO8..DO15  (bit0..bit7)
   • BU REGISTER: biz SET ETTİĞİMİZ çıkışları gösterir.

3) DI OKUMA — GetDI(id)
   • return: (0, level)   level = 1 veya 0
   • cl_dgt_input_l   → DI0..DI7   (bit0..bit7)
   • cl_dgt_input_h   → DI8..DI15  (bit0..bit7)
   • BU REGISTER: dışarıdan GELEN girişleri gösterir.
   • SDK'da gerçekten MEVCUT — XML-RPC yorum satırına alınmış,
     yerine realtime TCP paketindeki robot_state_pkg okunuyor.
     Bu daha hızlı ve güvenilir.

─────────────────────────────────────────────────────────────────
SİNYAL AKIŞI (app.py ile uyumlu)
─────────────────────────────────────────────────────────────────

  ADIM 1 : set_do(0, True)    → SetDO(0, 1)  robot "bardak al, başla"
  ADIM 2 : wait_di_true(1)    ← GetDI(1)==1  robottan "hazırım"
  ADIM 4 : set_do(2, True)    → SetDO(2, 1)  robot "içecek hazır, götür"
  ADIM 5 : wait_di_true(3)    ← GetDI(3)==1  robottan "teslim tamamlandı"

  HATA   : set_do(0, False)   → SetDO(0, 0)  temizlik
           set_do(2, False)   → SetDO(2, 0)  temizlik

─────────────────────────────────────────────────────────────────
True/False ↔ 1/0 ÖZET
─────────────────────────────────────────────────────────────────
  Yazma  :  True  → SetDO(id, 1)   |  False → SetDO(id, 0)
  Okuma  :  1     → HIGH (aktif)   |  0     → LOW  (pasif)
  Hata   : -1     → bağlantı yok / SDK hatası
"""

import time
import threading
from service.connect_robot import connect_robot
from sdk.Robot    import RPC as _RPC_CLASS  # is_conect class flag reset için

CHECK_INTERVAL_S = 2.0


class RobotManager:

    def __init__(self, robot_ip: str):
        self.robot_ip = robot_ip
        self.rpc = None
        self._stop = threading.Event()
        # RLock: _ensure_connected lock tutarken tekrar girebilir (deadlock önlemi)
        self._lock = threading.RLock()

    # ══════════════════════════════════════════════
    # YAŞAM DÖNGÜSÜ
    # ══════════════════════════════════════════════

    def start(self) -> None:
        print(f"[RobotManager] Başlatılıyor → {self.robot_ip}")
        self._ensure_connected()
        t = threading.Thread(target=self._monitor_loop, daemon=True, name="RobotMonitor")
        t.start()
        print("[RobotManager] İzleme thread'i başlatıldı.")

    def stop(self) -> None:
        print("[RobotManager] Durduruluyor...")
        self._stop.set()

    # ══════════════════════════════════════════════
    # BAĞLANTI YÖNETİMİ
    # ══════════════════════════════════════════════

    def _is_connected_quick(self) -> bool:
        """
        Hızlı bağlantı kontrolü.
        RLock sayesinde kilit içinden de çağrılabilir.

        Kontrol adımları:
          1) rpc nesnesi var mı?
          2) SDK realtime TCP soketi bağlı mı? (sock_cli_state_state)
          3) XML-RPC ping başarılı mı? (GetControllerIP)
        """
        if self.rpc is None:
            return False
        try:
            if not getattr(self.rpc, "sock_cli_state_state", False):
                return False
            err, ip = self.rpc.GetControllerIP()
            return err == 0 and bool(ip)
        except Exception:
            return False

    def _destroy_rpc(self) -> None:
        """
        Mevcut RPC nesnesini temiz şekilde kapatır.

        Robot enerjisi kesildiğinde veya bağlantı koptuğunda eski RPC
        nesnesinin thread'leri ve soketleri serbest bırakılmazsa yeni
        bağlantı kurulamaz. Bu fonksiyon:
          1) SDK iç thread'ini durdurur (stop_event)
          2) Realtime TCP soketini kapatır (sock_cli_state)
          3) SDK kapatma flag'ini set eder (closeRPC_state)
          4) RPC.is_conect class flag'ini True'ya sıfırlar
             ⚠️  KRİTİK: is_conect class-level değişken — False'ta kalırsa
             xmlrpc_timeout decorator tüm çağrıları -4 ile reddeder,
             yeni RPC nesnesi de bağlansa çalışmaz.
          5) self.rpc = None yapar
        """
        if self.rpc is None:
            return
        print("[RobotManager] 🔌 Eski RPC nesnesi kapatılıyor...")
        try:
            if hasattr(self.rpc, "stop_event"):
                self.rpc.stop_event.set()
        except Exception as e:
            print(f"[RobotManager]   stop_event hatası (yoksayıldı): {e}")
        try:
            sock = getattr(self.rpc, "sock_cli_state", None)
            if sock is not None:
                sock.close()
        except Exception as e:
            print(f"[RobotManager]   sock_cli_state kapatma hatası (yoksayıldı): {e}")
        try:
            if hasattr(self.rpc, "closeRPC_state"):
                self.rpc.closeRPC_state = True
        except Exception as e:
            print(f"[RobotManager]   closeRPC_state hatası (yoksayıldı): {e}")

        # ⚠️  is_conect CLASS değişkenini sıfırla
        # Robot.py __init__ içinde timeout olursa RPC.is_conect = False set edilir.
        # Bu class-level flag sonraki tüm RPC instance'larını etkiler.
        # Yeni bağlantı denemesinden ÖNCE True'ya döndürülmesi zorunlu.
        try:
            _RPC_CLASS.is_conect = True
            print("[RobotManager] 🔌 RPC.is_conect class flag sıfırlandı (True).")
        except Exception as e:
            print(f"[RobotManager]   is_conect reset hatası (yoksayıldı): {e}")

        self.rpc = None
        print("[RobotManager] 🔌 Eski RPC kapatıldı.")

    def _ensure_connected(self) -> None:
        """
        Bağlı değilse bağlanana kadar döner.
        Senkron — asyncio.to_thread ile çağrılmalıdır.

        Yeniden bağlantı akışı:
          1) Bağlı ise hemen dön.
          2) Eski RPC nesnesini _destroy_rpc() ile kapat.
             (is_conect flag sıfırlanır, eski thread/soket kapatılır)
          3) connect_robot() → TCP port testi → RPC() oluştur.
             Port kapalıysa (robot boot aşamasında) kısa bekle, tekrar dene.
             Port açılınca RPC() oluştur ve doğrula.
          4) Başarılıysa 1.5s bekle (realtime paket dolumu için).

        Not: connect_robot() içinde _tcp_reachable() ile port önce test
        edildiğinden gereksiz RPC() nesnesi oluşturulmaz, thread birikmez.
        """
        with self._lock:
            if self._is_connected_quick():
                return

            # Eski bozuk RPC nesnesini temizle (is_conect flag reset dahil)
            self._destroy_rpc()

            attempt = 0
            while not self._stop.is_set():
                attempt += 1
                print(f"[RobotManager] Bağlantı deneniyor #{attempt} → {self.robot_ip}")
                rpc, ok = connect_robot(self.robot_ip, retry=1, wait_s=1.0)
                if ok:
                    self.rpc = rpc
                    print("=" * 60)
                    print(f"[RobotManager] ✅ Robot Bağlantısı kuruldu (deneme #{attempt})")
                    print("=" * 60)
                    time.sleep(1.5)   # realtime state paketinin dolması için
                    return

                print(f"[RobotManager] ❌ Başarısız (#{attempt}), 5s sonra tekrar...")
                # Portu kapalıysa (robot boot aşaması) daha sık log istemiyoruz
                # 5s bekleyip tekrar dene — port açılınca connect_robot bağlanacak
                time.sleep(5)

            print("[RobotManager] _ensure_connected: stop sinyali geldi, çıkılıyor.")

    def _monitor_loop(self) -> None:
        """
        Bağlantıyı sürekli izler, koparsa yeniden bağlanır.

        Bağlantı kopma tespiti:
          - _is_connected_quick() → False
          - Otomatik olarak _ensure_connected() çağrılır
          - _ensure_connected() içinde eski RPC temizlenip yenisi oluşturulur
        """
        while not self._stop.is_set():
            ok = False
            with self._lock:
                ok = self._is_connected_quick()
            if not ok:
                print("[RobotManager] ⚠️  Bağlantı koptu — yeniden bağlanılıyor...")
                self._ensure_connected()
                if self.rpc is not None:
                    print("[RobotManager] ✅ Monitor: yeniden bağlantı başarılı.")
            time.sleep(CHECK_INTERVAL_S)

    # ══════════════════════════════════════════════
    # DO YAZMA  (biz → robot: çıkış sinyali)
    # ══════════════════════════════════════════════

    def set_do(self, do_id: int, status: bool) -> int:
        """
        Controller Digital Output set eder.

        SDK SetDO(id, status):
            status=1 → TRUE (HIGH)
            status=0 → FALSE (LOW)

        Returns:
            0  → başarı
           -1  → robot bağlı değil
           -2  → exception
        """
        with self._lock:
            if not self._is_connected_quick():
                self._ensure_connected()
            if not self._is_connected_quick():
                print(f"[RobotManager] ❌ set_do: Robot bağlı değil → DO{do_id} gönderilemedi.")
                return -1

            sdk_val = 1 if status else 0
            try:
                err = self.rpc.SetDO(int(do_id), sdk_val)
                err = int(err)
                label = "TRUE(1)" if status else "FALSE(0)"
                print(f"[RobotManager] 📤 SetDO(id={do_id}, status={sdk_val}) [{label}] → err={err}")
                return err
            except Exception as e:
                print(f"[RobotManager] ❌ set_do exception: {e}")
                return -2

    def send_true_signal(self, do_id: int = 0, tool_output: bool = False) -> int:
        """DO veya ToolDO'ya TRUE(1) gönderir."""
        with self._lock:
            if not self._is_connected_quick():
                self._ensure_connected()
            if not self._is_connected_quick():
                return -1
            try:
                if tool_output:
                    err = self.rpc.SetToolDO(int(do_id), 1)
                    print(f"[RobotManager] 📤 SetToolDO({do_id}, 1) [TRUE] → err={err}")
                else:
                    err = self.rpc.SetDO(int(do_id), 1)
                    print(f"[RobotManager] 📤 SetDO({do_id}, 1) [TRUE] → err={err}")
                return int(err)
            except Exception as e:
                print(f"[RobotManager] ❌ send_true_signal exception: {e}")
                return -2

    def send_false_signal(self, do_id: int = 0, tool_output: bool = False) -> int:
        """DO veya ToolDO'ya FALSE(0) gönderir."""
        with self._lock:
            if not self._is_connected_quick():
                self._ensure_connected()
            if not self._is_connected_quick():
                return -1
            try:
                if tool_output:
                    err = self.rpc.SetToolDO(int(do_id), 0)
                    print(f"[RobotManager] 📤 SetToolDO({do_id}, 0) [FALSE] → err={err}")
                else:
                    err = self.rpc.SetDO(int(do_id), 0)
                    print(f"[RobotManager] 📤 SetDO({do_id}, 0) [FALSE] → err={err}")
                return int(err)
            except Exception as e:
                print(f"[RobotManager] ❌ send_false_signal exception: {e}")
                return -2

    # ══════════════════════════════════════════════
    # DO OKUMA  (biz set ettiğimiz çıkışları geri okuma)
    # ══════════════════════════════════════════════

    def read_do_status(self, do_id: int) -> int:
        """
        Controller DO (çıkış) register'ını okur.

        SDK GetDO() → (0, [cl_dgt_output_h, cl_dgt_output_l])
            cl_dgt_output_l → DO0..DO7  (bit0..bit7)
            cl_dgt_output_h → DO8..DO15 (bit0..bit7)

        NOT: Biz SET ettiğimiz değerleri döndürür.
             Robottan gelen sinyal için read_di_status() kullanın.

        Returns:
            1  → HIGH (aktif, TRUE)
            0  → LOW  (pasif, FALSE)
           -1  → hata
        """
        with self._lock:
            if not self._is_connected_quick():
                self._ensure_connected()
            if not self._is_connected_quick():
                return -1

            try:
                err, states = self.rpc.GetDO()
                if err != 0 or states is None or len(states) < 2:
                    print(f"[RobotManager] ❌ read_do_status: GetDO() hata err={err}")
                    return -1

                do_id = int(do_id)
                do_h  = int(states[0])   # DO8..15
                do_l  = int(states[1])   # DO0..7

                if 0 <= do_id <= 7:
                    return (do_l >> do_id) & 1
                elif 8 <= do_id <= 15:
                    return (do_h >> (do_id - 8)) & 1
                else:
                    print(f"[RobotManager] ❌ read_do_status: id aralık dışı → {do_id}")
                    return -1
            except Exception as e:
                print(f"[RobotManager] ❌ read_do_status exception: {e}")
                return -1

    # ══════════════════════════════════════════════
    # DI OKUMA  (robot → biz: giriş sinyali)
    # ══════════════════════════════════════════════

    def read_di_status(self, di_id: int) -> int:
        """
        Controller DI (giriş) register'ını okur.

        SDK GetDI(id) → (0, level)
            cl_dgt_input_l → DI0..DI7  (bit0..bit7)
            cl_dgt_input_h → DI8..DI15 (bit0..bit7)
            level = 1 (HIGH/aktif) veya 0 (LOW/pasif)

        DOĞRULAMA: SDK'da GetDI() gerçekten mevcut ve çalışıyor.
        realtime TCP paketi (robot_state_pkg) üzerinden okunuyor.

        Returns:
            1  → HIGH (sinyal var, aktif, TRUE)
            0  → LOW  (sinyal yok, pasif, FALSE)
           -1  → hata (id aralık dışı, bağlantı yok)
        """
        with self._lock:
            if not self._is_connected_quick():
                self._ensure_connected()
            if not self._is_connected_quick():
                return -1

            try:
                err, level = self.rpc.GetDI(int(di_id))
                if err != 0:
                    print(f"[RobotManager] ❌ read_di_status: GetDI({di_id}) hata err={err}")
                    return -1
                return int(level)   # 1=HIGH/TRUE, 0=LOW/FALSE
            except Exception as e:
                print(f"[RobotManager] ❌ read_di_status exception: {e}")
                return -1

    # ══════════════════════════════════════════════
    # BEKLEME FONKSİYONLARI
    # ══════════════════════════════════════════════

    def wait_di_true(self, di_id: int, timeout_s: float = 60.0, poll_s: float = 0.1) -> bool:
        """
        Robottan gelen DI sinyali HIGH(1) olana kadar bekler.

        GetDI() → cl_dgt_input register → robottan gelen sinyaller.

        Kullanım:
            wait_di_true(1) → DI1=1 bekle (robot hazır sinyali)
            wait_di_true(3) → DI3=1 bekle (robot teslim tamamladı)

        Returns:
            True  → sinyal geldi (DI=1, HIGH)
            False → timeout
        """
        deadline = time.time() + timeout_s
        di_id    = int(di_id)
        last_log = 0.0

        print(f"[RobotManager] ⏳ DI{di_id}=HIGH(1) bekleniyor (timeout={timeout_s}s)...")

        while time.time() < deadline:
            val = self.read_di_status(di_id)

            if val == 1:
                print(f"[RobotManager] ✅ DI{di_id} = HIGH(1) — sinyal alındı.")
                return True

            if val == -1:
                print(f"[RobotManager] ⚠️  DI{di_id} okunamadı (bağlantı?), bekleniyor...")
                time.sleep(0.5)
                continue

            # Her 5s'de bir log (spam önleme)
            now = time.time()
            if now - last_log >= 5.0:
                print(f"[RobotManager] ⏳ DI{di_id}=LOW(0), bekleniyor... (kalan {deadline-now:.0f}s)")
                last_log = now

            time.sleep(poll_s)

        print(f"[RobotManager] ⏰ Timeout: DI{di_id} {timeout_s}s içinde HIGH(1) olmadı.")
        return False

    def wait_do_true(self, do_id: int, timeout_s: float = 60.0, poll_s: float = 0.1) -> bool:
        """
        DO (çıkış) register'ının HIGH(1) olmasını bekler.

        ⚠️  NOT: Biz SET ettiğimiz çıkışı okur.
        Robottan gelen sinyal için wait_di_true() kullanın.
        Geriye dönük uyumluluk için bırakıldı.
        """
        deadline = time.time() + timeout_s
        do_id    = int(do_id)
        last_log = 0.0

        print(f"[RobotManager] ⏳ DO{do_id}=HIGH(1) bekleniyor [çıkış reg.] (timeout={timeout_s}s)...")

        while time.time() < deadline:
            val = self.read_do_status(do_id)

            if val == 1:
                print(f"[RobotManager] ✅ DO{do_id} = HIGH(1) [çıkış].")
                return True

            now = time.time()
            if now - last_log >= 5.0:
                print(f"[RobotManager] ⏳ DO{do_id}=LOW(0) [çıkış], bekleniyor... (kalan {deadline-now:.0f}s)")
                last_log = now

            time.sleep(poll_s)

        print(f"[RobotManager] ⏰ Timeout: DO{do_id} {timeout_s}s içinde HIGH(1) olmadı.")
        return False

    # ══════════════════════════════════════════════
    # TOOL DO
    # ══════════════════════════════════════════════

    def read_tool_do(self, do_id: int) -> int:
        """Tool DO (çıkış) okur. Returns: 1/0 veya -1"""
        with self._lock:
            if not self._is_connected_quick():
                self._ensure_connected()
            if not self._is_connected_quick():
                return -1
            try:
                err, states = self.rpc.GetToolDO()
                if err != 0:
                    return -1
                return int(states[int(do_id)])
            except Exception as e:
                print(f"[RobotManager] ❌ read_tool_do exception: {e}")
                return -1

    # ══════════════════════════════════════════════
    # HAREKET
    # ══════════════════════════════════════════════

    def moveL_xyz_keep_orientation(self, x, y, z, tool=0, user=0, vel=20.0):
        with self._lock:
            if not self._is_connected_quick():
                print("[RobotManager] ❌ MoveL: Robot bağlı değil.")
                return -1
            cur = self.rpc.robot_state_pkg.tl_cur_pos
            rx, ry, rz = float(cur[3]), float(cur[4]), float(cur[5])
            target = [float(x), float(y), float(z), rx, ry, rz]
            err = self.rpc.MoveL(target, tool, user, vel=vel, blendR=-1.0)
            print(f"[RobotManager] ➡️  MoveL target={target} | err={err}")
            return err

    # ══════════════════════════════════════════════
    # DURUM
    # ══════════════════════════════════════════════

    def get_mode(self) -> dict:
        """
        Robotun anlık mod ve program durumunu döner.
        Tüm değerler realtime TCP paketi (robot_state_pkg) üzerinden okunur
        — XML-RPC çağrısı yapılmaz, gecikme yoktur.

        robot_mode (otomatik / manuel):
            0 → Otomatik mod  — sipariş akışı başlatılabilir
            1 → Manuel mod    — sipariş akışı BAŞLATILMAMALI

        program_state (program çalışma durumu):
            1 → Durdu
            2 → Çalışıyor
            3 → Duraklatıldı

        robot_state (robot hareket durumu):
            1 → Durdu
            2 → Çalışıyor
            3 → Duraklatıldı
            4 → Drag / sürükleme modu

        Returns:
            {
                "connected"    : bool,
                "robot_mode"   : int | None,   # 0=Otomatik  1=Manuel
                "program_state": int | None,   # 1=Durdu  2=Çalışıyor  3=Duraklatıldı
                "robot_state"  : int | None,   # 1=Durdu  2=Çalışıyor  3=Duraklatıldı  4=Drag
                "mode_label"   : str,          # "auto" | "manual" | "disconnected" | "error"
                "program_label": str,          # "stopped" | "running" | "paused" | "unknown"
                "state_label"  : str,          # "stopped" | "running" | "paused" | "drag" | "unknown"
            }
        """
        _PROGRAM_LABELS = {1: "stopped", 2: "running", 3: "paused"}
        _STATE_LABELS   = {1: "stopped", 2: "running", 3: "paused", 4: "drag"}

        with self._lock:
            if not self._is_connected_quick():
                return {
                    "connected"    : False,
                    "robot_mode"   : None,
                    "program_state": None,
                    "robot_state"  : None,
                    "mode_label"   : "disconnected",
                    "program_label": "disconnected",
                    "state_label"  : "disconnected",
                }
            try:
                pkg  = self.rpc.robot_state_pkg
                mode = int(pkg.robot_mode)      # 0=Otomatik  1=Manuel
                prog = int(pkg.program_state)   # 1=Durdu  2=Çalışıyor  3=Duraklatıldı
                rs   = int(pkg.robot_state)     # 1=Durdu  2=Çalışıyor  3=Duraklatıldı  4=Drag

                result = {
                    "connected"    : True,
                    "robot_mode"   : mode,
                    "program_state": prog,
                    "robot_state"  : rs,
                    "mode_label"   : "auto" if mode == 0 else "manual",
                    "program_label": _PROGRAM_LABELS.get(prog, f"unknown:{prog}"),
                    "state_label"  : _STATE_LABELS.get(rs,   f"unknown:{rs}"),
                }
                print(
                    f"[RobotManager] get_mode → "
                    f"mode={mode}({result['mode_label']}) "
                    f"program={prog}({result['program_label']}) "
                    f"state={rs}({result['state_label']})"
                )
                return result

            except Exception as e:
                print(f"[RobotManager] ❌ get_mode exception: {e}")
                return {
                    "connected"    : False,
                    "robot_mode"   : None,
                    "program_state": None,
                    "robot_state"  : None,
                    "mode_label"   : "error",
                    "program_label": "error",
                    "state_label"  : "error",
                }

    def get_robot_mode_safe(self) -> str:
        """
        Geriye dönük uyumluluk için korundu.
        Yeni kod için get_mode() kullanın — robot_mode (otomatik/manuel) dahil
        tüm durum bilgilerini dict olarak döner.

        Bu fonksiyon yalnızca robot_state (hareket durumu) okur;
        robot_mode (otomatik/manuel) okumaz.

        Returns: 'running' | 'stopped' | 'paused' | 'drag' | 'disconnected' | 'error'
        """
        info = self.get_mode()
        if not info["connected"]:
            return info["mode_label"]  # "disconnected" veya "error"
        return info["state_label"]

    # ══════════════════════════════════════════════
    # MOD AYARLAMA
    # ══════════════════════════════════════════════

    def set_mode(self, mode: int) -> int:
        """
        Robotun çalışma modunu değiştirir.

        mode:
            0 → Otomatik mod
            1 → Manuel mod

        SDK Mode(state) XML-RPC çağrısı yapar.

        Returns:
            0  → başarı
           -1  → robot bağlı değil
           -2  → exception
        """
        with self._lock:
            if not self._is_connected_quick():
                self._ensure_connected()
            if not self._is_connected_quick():
                print(f"[RobotManager] ❌ set_mode: Robot bağlı değil.")
                return -1
            try:
                err = self.rpc.Mode(int(mode))
                label = "Otomatik(0)" if mode == 0 else "Manuel(1)"
                print(f"[RobotManager] 📤 Mode({mode}) [{label}] → err={err}")
                return int(err)
            except Exception as e:
                print(f"[RobotManager] ❌ set_mode exception: {e}")
                return -2

    def set_auto_mode_and_wait(self, timeout_s: float = 10.0, poll_s: float = 0.3) -> bool:
        """
        Robotu otomatik moda (robot_mode=0) alır ve geçişi bekler.

        1) Mode(0) çağrısı yapar.
        2) robot_state_pkg.robot_mode == 0 olana kadar polling yapar.
        3) timeout_s içinde geçiş olmazsa False döner.

        Returns:
            True  → robot otomatik modda
            False → timeout veya bağlantı hatası
        """
        print(f"[RobotManager] ⏳ Otomatik moda geçiş isteniyor (timeout={timeout_s}s)...")

        err = self.set_mode(0)
        if err not in (0, -2):   # -2 zaten exception, yine de bekle
            if err != 0:
                print(f"[RobotManager] ⚠️  Mode(0) err={err} — yine de bekleniyor.")

        deadline = time.time() + timeout_s
        while time.time() < deadline:
            info = self.get_mode()
            if not info["connected"]:
                time.sleep(poll_s)
                continue
            if info["robot_mode"] == 0:
                print(f"[RobotManager] ✅ Robot otomatik moda geçti.")
                return True
            time.sleep(poll_s)

        print(f"[RobotManager] ⏰ Otomatik mod geçiş timeout ({timeout_s}s).")
        return False

    # ══════════════════════════════════════════════
    # ROBOT DURUM ÖNBELLEK (thread-safe)
    # ══════════════════════════════════════════════

    def get_robot_status(self) -> dict:
        """
        Robotun frontend için anlık durum özetini döner.
        Machine monitor benzeri — polling ile çağrılabilir.

        Dönen alanlar:
            connected    : bool
            robot_mode   : int | None    0=Otomatik  1=Manuel
            program_state: int | None
            robot_state  : int | None
            mode_label   : str           "auto" | "manual" | "disconnected"
            program_label: str           "stopped" | "running" | "paused"
            state_label  : str           "stopped" | "running" | "paused" | "drag"
            can_order    : bool          True → sipariş verilebilir
                                         (connected + auto + running)
        """
        info = self.get_mode()
        can_order = (
            info["connected"] and
            info["robot_mode"] == 0 and        # otomatik mod
            info["robot_state"] in (1, 2)      # durdu veya çalışıyor (bekleniyor/hazır)
        )
        info["can_order"] = can_order
        return info



    def stop_motion(self) -> int:
        """
        Anlık hareketi durdurur (programı değil, sadece hareketi).
        SDK: StopMotion()
        Returns: 0=başarı, -1=bağlı değil, -2=exception
        """
        with self._lock:
            if not self._is_connected_quick():
                self._ensure_connected()
            if not self._is_connected_quick():
                print("[RobotManager] ❌ stop_motion: Robot bağlı değil.")
                return -1
            try:
                err = self.rpc.StopMotion()
                print(f"[RobotManager] 📤 StopMotion() → err={err}")
                return int(err)
            except Exception as e:
                print(f"[RobotManager] ❌ stop_motion exception: {e}")
                return -2

    # ══════════════════════════════════════════════
    # PROGRAM KONTROLÜ
    # ══════════════════════════════════════════════
    # Robot üzerinde yüklü programı başlatır / durdurur /
    # duraklatır / devam ettirir.
    #
    # Ön koşul: robot otomatik modda olmalı (robot_mode == 0).
    # Program yüklü değilse ProgramRun hata döner.
    #
    # program_state değerleri (robot_state_pkg):
    #   1 → Durdu / program yok
    #   2 → Çalışıyor
    #   3 → Duraklatıldı
    # ══════════════════════════════════════════════

    def _sdk_call(self, fn_name: str, *args) -> int:
        """
        İç yardımcı: bağlantı kontrol + SDK çağrısı + loglama.
        Tüm program kontrol fonksiyonları bunu kullanır.
        """
        with self._lock:
            if not self._is_connected_quick():
                self._ensure_connected()
            if not self._is_connected_quick():
                print(f"[RobotManager] ❌ {fn_name}: Robot bağlı değil.")
                return -1
            try:
                fn  = getattr(self.rpc, fn_name)
                err = fn(*args) if args else fn()
                err = int(err)
                print(f"[RobotManager] 📤 {fn_name}({', '.join(str(a) for a in args)}) → err={err}")
                return err
            except Exception as e:
                print(f"[RobotManager] ❌ {fn_name} exception: {e}")
                return -2

    def program_run(self) -> int:
        """
        Yüklü programı başlatır.
        SDK: ProgramRun()
        Ön koşul: robot otomatik modda olmalı.

        Returns:
            0  → başarı (program çalışmaya başladı)
           -1  → robot bağlı değil
           -2  → exception
           >0  → SDK hata kodu
        """
        return self._sdk_call("ProgramRun")

    def program_stop(self) -> int:
        """
        Çalışan programı durdurur.
        SDK: ProgramStop()
        Durdurulan program sıfırdan başlatılabilir (ProgramRun).

        Returns:
            0  → başarı
           -1  → robot bağlı değil
           -2  → exception
           >0  → SDK hata kodu
        """
        return self._sdk_call("ProgramStop")

    def program_pause(self) -> int:
        """
        Çalışan programı duraklatır.
        SDK: ProgramPause()
        Devam ettirmek için program_resume() kullanın.

        Returns:
            0  → başarı
           -1  → robot bağlı değil
           -2  → exception
           >0  → SDK hata kodu
        """
        return self._sdk_call("ProgramPause")

    def program_resume(self) -> int:
        """
        Duraklatılmış programı devam ettirir.
        SDK: ProgramResume()

        Returns:
            0  → başarı
           -1  → robot bağlı değil
           -2  → exception
           >0  → SDK hata kodu
        """
        return self._sdk_call("ProgramResume")

    def set_manual_mode(self) -> bool:
        """
        Robotu manuel moda alır ve geçişi bekler.
        set_auto_mode_and_wait() ile aynı mantık, Mode(1).

        Returns:
            True  → manuel modda
            False → timeout veya bağlantı hatası
        """
        print("[RobotManager] ⏳ Manuel moda geçiş isteniyor...")
        err = self.set_mode(1)
        if err not in (0,):
            print(f"[RobotManager] ⚠️  Mode(1) err={err} — yine de bekleniyor.")

        deadline = time.time() + 10.0
        while time.time() < deadline:
            info = self.get_mode()
            if not info["connected"]:
                time.sleep(0.3)
                continue
            if info["robot_mode"] == 1:
                print("[RobotManager] ✅ Robot manuel moda geçti.")
                return True
            time.sleep(0.3)

        print("[RobotManager] ⏰ Manuel mod geçiş timeout (10s).")
        return False
