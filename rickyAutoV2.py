import pyautogui
import win32gui
import win32con
import time
import sys
import os
import cv2
import numpy as np
import threading

is_processing = False
processing_lock = threading.Lock()


# 资源路径处理，支持打包后读取嵌入的图片
def resource_path(relative_path):
    """ 获取资源的绝对路径，兼容源码运行和PyInstaller打包后的exe运行 """
    try:
        # PyInstaller打包后，会把文件解压到临时目录，_MEIPASS就是临时目录的路径
        base_path = sys._MEIPASS
    except Exception:
        # 源码运行时，用当前目录
        base_path = os.path.abspath("./1600pic")

    return os.path.join(base_path, relative_path)


# 加载图片，支持中文路径，解决opencv不支持中文路径的问题
def load_image(path):
    # 用Python的原生open读取文件，支持中文路径
    with open(path, 'rb') as f:
        data = f.read()
    # 转成numpy数组
    arr = np.frombuffer(data, np.uint8)
    # 解码成图片，避免opencv的imread不支持中文路径的问题
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


# 配置：按钮截图的文件名
ACCEPT_IMG_1 = resource_path("accept.jpg")
ACCEPT_IMG_2 = resource_path("accept2.jpg")
CONFIRM_IMG = resource_path("confirm.jpg")
CONFIRM_IMG_2 = resource_path("confirm2.jpg")
RECONNECT_IMG = resource_path("recon.jpg")
NO_IMG = resource_path("no.jpg")
NO_IMG_2 = resource_path("no2.jpg")
READY_IMG = resource_path("ready.jpg")
END_IMG = resource_path("end.jpg")
UPDATE_IMG = resource_path("update.jpg")
ERROR_IMG = resource_path("error.jpg")

# 图像匹配的精度（0~1，越高要求越严格，建议0.7~0.8）
CONFIDENCE = 0.7
# 检测间隔（秒）
CHECK_INTERVAL = 2
# 点击后的冷却时间（避免重复点击，秒）
COOLDOWN = 0.5
# 窗口检测
WINDOW_CHECK_INTERVAL = 2

recon_count = 0
REC_MAX = 10

accept_img = load_image(ACCEPT_IMG_1)
accept_img_2 = load_image(ACCEPT_IMG_2)
confirm_img = load_image(CONFIRM_IMG)
confirm_img_2 = load_image(CONFIRM_IMG_2)
rec_img = load_image(RECONNECT_IMG)
no_img = load_image(NO_IMG)
no_img_2 = load_image(NO_IMG_2)
ready_img = load_image(READY_IMG)
end_img = load_image(END_IMG)
update_img = load_image(UPDATE_IMG)
error_img = load_image(ERROR_IMG)


def get_dota_window():
    """
    自动查找Dota2的窗口，支持中英文标题
    """
    hwnds = []

    def callback(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            # 匹配英文Dota2或者中文刀塔2的窗口标题
            if "Dota" in title or "刀塔" in title:
                extra.append(hwnd)
        return True

    win32gui.EnumWindows(callback, hwnds)
    return hwnds[0] if hwnds else None


def restore_dota_window():
    """恢复最小化的Dota2窗口（不主动抢占前台，只恢复显示）"""
    dota_hwnd = get_dota_window()
    if dota_hwnd and win32gui.IsIconic(dota_hwnd):
        print(f"[{time.strftime('%H:%M:%S')}] 检测到Dota2窗口被最小化，自动恢复...")
        win32gui.ShowWindow(dota_hwnd, win32con.SW_RESTORE)
        return True
    return False


def activate_dota_window():
    """
    激活Dota2窗口：如果最小化就恢复，然后放到前台
    解决Windows前台窗口权限限制的问题
    """
    hwnd = get_dota_window()
    if not hwnd:
        print("未找到Dota2窗口，请先启动游戏！")
        return False

    # 先恢复最小化窗口
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

    try:
        # 先尝试直接设置前台
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        # 如果失败，通过模拟Alt键绕过系统的前台锁限制
        try:
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
            shell.SendKeys('%')  # 发送Alt键，欺骗系统允许前台切换
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            # 如果还是失败，不影响后续检测，只是窗口可能不在前台
            print("警告：无法将Dota2窗口前置，点击可能无效")

    return True


def window_maintain_thread():
    """独立的窗口维护线程：低频率检测，仅恢复最小化窗口"""
    while True:
        try:
            dota_hwnd = get_dota_window()
            if not dota_hwnd:
                print(f"[{time.strftime('%H:%M:%S')}] 未检测到Dota2窗口，自动启动游戏...")
                os.startfile("steam://rungameid/570")
                time.sleep(15)  # 等游戏启动
                continue
            if dota_hwnd and win32gui.IsIconic(dota_hwnd):
                print(f"[{time.strftime('%H:%M:%S')}] 检测到Dota2窗口被最小化，自动恢复...")
                win32gui.ShowWindow(dota_hwnd, win32con.SW_RESTORE)

        except Exception as e:

            pass
        time.sleep(WINDOW_CHECK_INTERVAL)


def check_reconnect_thread():
    global is_processing, recon_count
    while True:
        if is_processing:
            time.sleep(0.1)
            continue
        try:
            reconnect_pos = pyautogui.locateOnScreen(
                rec_img,
                confidence=CONFIDENCE
            )
            if reconnect_pos:

                with processing_lock:
                    is_processing = True
                print(f"[{time.strftime('%H:%M:%S')}] 检测到掉线，点击重新连接...")
                # 临时激活Dota2窗口
                activate_dota_window()
                time.sleep(0.1)
                pyautogui.click(pyautogui.center(reconnect_pos))
                recon_count += 1
                time.sleep(COOLDOWN)
                with processing_lock:
                    is_processing = False

                if recon_count > REC_MAX:
                    with processing_lock:
                        is_processing = True

                    print(f"[{time.strftime('%H:%M:%S')}] 连续{recon_count}次重连失败，自动重启Dota2...")
                    os.system("taskkill /f /im dota2.exe")
                    time.sleep(3)
                    # os.startfile("steam://rungameid/570")
                    # time.sleep(10)
                    recon_count = 0
                    with processing_lock:
                        is_processing = False

        except Exception as e:
            pass
        time.sleep(CHECK_INTERVAL)


def check_accept_thread():
    global is_processing
    while True:
        if is_processing:
            time.sleep(0.1)
            continue
        try:
            accept_match_pos = pyautogui.locateOnScreen(
                accept_img,
                confidence=CONFIDENCE
            )
            if accept_match_pos:
                with processing_lock:
                    is_processing = True
                print(f"[{time.strftime('%H:%M:%S')}] 检测到游戏开局，点击接受...")
                activate_dota_window()
                time.sleep(0.1)
                pyautogui.click(pyautogui.center(accept_match_pos))
                time.sleep(COOLDOWN)
                with processing_lock:
                    is_processing = False
        except Exception as e:
            pass
        time.sleep(CHECK_INTERVAL)


def check_invite_thread():
    global is_processing
    while True:
        if is_processing:
            time.sleep(0.1)
            continue
        try:
            accept_invite_pos = pyautogui.locateOnScreen(
                accept_img_2,
                confidence=CONFIDENCE
            )
            if accept_invite_pos:
                with processing_lock:
                    is_processing = True
                print(f"[{time.strftime('%H:%M:%S')}] 检测到好友邀请，点击接受...")
                activate_dota_window()
                time.sleep(0.1)
                pyautogui.click(pyautogui.center(accept_invite_pos))
                time.sleep(COOLDOWN)
                with processing_lock:
                    is_processing = False
        except Exception as e:
            pass
        time.sleep(CHECK_INTERVAL)


def check_confirm_thread():
    global is_processing
    while True:
        if is_processing:
            time.sleep(0.1)
            continue
        try:
            update_pos = pyautogui.locateOnScreen(
                update_img,
                confidence=CONFIDENCE
            )
            if update_pos:
                with processing_lock:
                    is_processing = True
                print(f"[{time.strftime('%H:%M:%S')}] 检测到游戏更新通知，正在自动重启游戏进行更新...")
                # 强制关闭Dota2进程
                os.system("taskkill /f /im dota2.exe")
                time.sleep(3)
                # 启动Steam的Dota2，自动触发更新
                # os.startfile("steam://rungameid/570")
                # time.sleep(10)
                with processing_lock:
                    is_processing = False
                continue
        except Exception as e:
            pass

        try:
            error_pos = pyautogui.locateOnScreen(
                error_img,
                confidence=CONFIDENCE
            )
            if error_pos:
                with processing_lock:
                    is_processing = True
                print(f"[{time.strftime('%H:%M:%S')}] 检测到游戏错误通知，正在自动重启游戏...")
                # 强制关闭Dota2进程
                os.system("taskkill /f /im dota2.exe")
                time.sleep(3)
                # 启动Steam的Dota2，自动触发更新
                # os.startfile("steam://rungameid/570")
                # time.sleep(10)
                with processing_lock:
                    is_processing = False
                continue
        except Exception as e:
            pass

        try:
            # 没有更新，再检测确定按钮
            ok_pos = pyautogui.locateOnScreen(
                confirm_img,
                confidence=CONFIDENCE
            )
            if ok_pos:
                with processing_lock:
                    is_processing = True
                print(f"[{time.strftime('%H:%M:%S')}] 检测到确定按钮，点击确定...")
                activate_dota_window()
                time.sleep(0.1)
                pyautogui.click(pyautogui.center(ok_pos))
                time.sleep(COOLDOWN)
                with processing_lock:
                    is_processing = False
        except Exception as e:
            pass

        try:
            ok_pos2 = pyautogui.locateOnScreen(
                confirm_img_2,
                confidence=CONFIDENCE
            )
            if ok_pos2:
                with processing_lock:
                    is_processing = True
                print(f"[{time.strftime('%H:%M:%S')}] 检测到确定按钮，点击确定...")
                activate_dota_window()
                time.sleep(0.1)
                pyautogui.click(pyautogui.center(ok_pos2))
                time.sleep(COOLDOWN)
                with processing_lock:
                    is_processing = False
        except Exception as e:
            pass
        time.sleep(CHECK_INTERVAL)


def check_ready_thread():
    global is_processing
    while True:
        if is_processing:
            time.sleep(0.1)
            continue
        try:
            accept_ready_pos = pyautogui.locateOnScreen(
                ready_img,
                confidence=CONFIDENCE
            )
            if accept_ready_pos:
                with processing_lock:
                    is_processing = True
                print(f"[{time.strftime('%H:%M:%S')}] 检测到就绪按钮，点击就绪...")
                activate_dota_window()
                time.sleep(0.1)
                pyautogui.click(pyautogui.center(accept_ready_pos))
                time.sleep(COOLDOWN)
                with processing_lock:
                    is_processing = False
        except Exception as e:
            pass
        time.sleep(CHECK_INTERVAL)


def check_no_thread():
    global is_processing
    while True:
        if is_processing:
            time.sleep(0.1)
            continue
        try:
            accept_no_pos = pyautogui.locateOnScreen(
                no_img,
                confidence=CONFIDENCE
            )
            if accept_no_pos:
                with processing_lock:
                    is_processing = True
                print(f"[{time.strftime('%H:%M:%S')}] 检测到关闭按钮，点击关闭...")
                activate_dota_window()
                time.sleep(0.1)
                pyautogui.click(pyautogui.center(accept_no_pos))
                time.sleep(COOLDOWN)
                with processing_lock:
                    is_processing = False
        except Exception as e:
            pass

        try:
            accept_no_pos2 = pyautogui.locateOnScreen(
                no_img_2,
                confidence=CONFIDENCE
            )
            if accept_no_pos2:
                with processing_lock:
                    is_processing = True
                print(f"[{time.strftime('%H:%M:%S')}] 检测到观战按钮，点击否...")
                activate_dota_window()
                time.sleep(0.1)
                pyautogui.click(pyautogui.center(accept_no_pos2))
                time.sleep(COOLDOWN)
                with processing_lock:
                    is_processing = False
        except Exception as e:
            pass
        time.sleep(CHECK_INTERVAL)


def check_end_thread():
    global is_processing
    while True:
        if is_processing:
            time.sleep(0.1)
            continue
        try:
            accept_end_pos = pyautogui.locateOnScreen(
                end_img,
                confidence=CONFIDENCE
            )
            if accept_end_pos:
                with processing_lock:
                    is_processing = True
                print(f"[{time.strftime('%H:%M:%S')}] 检测到游戏结束，点击继续...")
                activate_dota_window()
                time.sleep(0.1)
                pyautogui.click(pyautogui.center(accept_end_pos))
                time.sleep(COOLDOWN)
                with processing_lock:
                    is_processing = False
        except Exception as e:
            pass
        time.sleep(CHECK_INTERVAL)



def main():
    print("-" * 50)
    print("这是橙子头ricky制作的自动接受、自动重连、自动更新脚本")
    print("This is a dota2 script including AUTO ACCEPT, AUTO RECONNECT, AUTO UPDATE from ricky_Orange_Head")
    print("请把Dota2客户端设置成 1600*900p 窗口模式！语言仅支持中文！")
    print("Please set Dota2 1600*900p windowed, Chinese Language")
    print("脚本运行期间不要关闭小黑框！")
    print("Keep small black window on!")
    print("脚本仅模拟鼠标点击，不会修改游戏数据，理论上不会触发 VAC 封禁")
    print("The script only simulates mouse clicks and does not modify game data, so theoretically it should not trigger a VAC ban.")
    print("按 Ctrl+C 可以退出程序")
    print("Press Ctrl+C to end the script")
    print("-" * 50)

    # 开启pyautogui的紧急停止：鼠标移到左上角会自动终止脚本
    pyautogui.FAILSAFE = True

    # 启动前先检查截图文件是否存在
    # import os
    # for img_path in [
    #     ACCEPT_IMG_1,
    #     ACCEPT_IMG_2,
    #     CONFIRM_IMG,
    #     CONFIRM_IMG_2,
    #     RECONNECT_IMG,
    #     NO_IMG,
    #     NO_IMG_2,
    #     READY_IMG,
    #     UPDATE_IMG,
    # ]:
    #     if not os.path.exists(img_path):
    #         print(f"错误：未找到截图文件 {img_path}，请先准备好按钮截图并和脚本放在同一个文件夹！")
    #         return

    # 启动所有线程
    threads = [
        threading.Thread(target=window_maintain_thread, daemon=True),
        threading.Thread(target=check_reconnect_thread, daemon=True),
        threading.Thread(target=check_accept_thread, daemon=True),
        threading.Thread(target=check_invite_thread, daemon=True),
        threading.Thread(target=check_confirm_thread, daemon=True),
        threading.Thread(target=check_ready_thread, daemon=True),
        threading.Thread(target=check_no_thread, daemon=True),
        threading.Thread(target=check_end_thread, daemon=True),
    ]
    for t in threads:
        t.start()

    # 主线程等待退出
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n" + "-" * 50)
        print("程序已正常退出。")

# pyinstaller --onefile --add-data "./1920pic/accept.jpg;." --add-data "./1920pic/accept2.jpg;." --add-data "./1920pic/confirm.jpg;." --add-data "./1920pic/confirm2.jpg;." --add-data "./1920pic/recon.jpg;." --add-data "./1920pic/no.jpg;." --add-data "./1920pic/no2.jpg;." --add-data "./1920pic/ready.jpg;." --add-data "./1920pic/end.jpg;." --add-data "./1920pic/error.jpg;." --add-data "./1920pic/update.jpg;." rickyAutoV2.py



if __name__ == "__main__":
    main()