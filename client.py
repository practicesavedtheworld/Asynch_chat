import asyncio
import logging
import os
import random
import re
import sys
from asyncio import StreamReader, StreamWriter
from collections import namedtuple
from typing import Optional

import aiofiles
import aiohttp
import magic

from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QColor
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtWidgets import QVBoxLayout, QLineEdit, QListView, QFileDialog, QApplication

from Exceptions import WrongKeyEntered


class Ui(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()
        uic.loadUi('GUI.ui', self)
        self.show()

        self.rand_number = random.randint(1, 6)
        self.sender_message = namedtuple('sender_message', ['sender', 'message'])
        self.__last_sent_message: Optional[tuple[str, str]] = None
        self.queue = asyncio.Queue()
        self._tasks: list[asyncio.Task] = []
        self._files = {}
        self.magic_obj = magic.Magic()

        self.reader: Optional[StreamReader] = None
        self.writer: Optional[StreamWriter] = None

        self.model = QStandardItemModel()

        self.list_view: QListView = self.message_view_box
        self.list_view.setModel(self.model)
        self.list_view.setAutoScroll(True)
        self.list_view.doubleClicked.connect(self.on_list_view_double_clicked)

        self.line_edit: QLineEdit = self.message_enter_box
        self.line_edit.keyPressEvent = self.my_keyPressEvent
        self.line_edit.returnPressed.connect(self.write_message)
        self.clear_button.clicked.connect(self.clear_view_box)

        self.message_enter_box.returnPressed.connect(self.write_message)
        self.send_button.clicked.connect(self.write_message)

        self.file_uploader.clicked.connect(self.file_handler)

        self.timer: QTimer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.get_clients_count_callback)

        self.wake_up_button.clicked.connect(self.play_audio)
        self.media_player = QMediaPlayer(self)

        self.layout: QVBoxLayout = QVBoxLayout()
        self.layout.addWidget(self.list_view)
        self.layout.addWidget(self.line_edit)

        self.setLayout(self.layout)

    def _default_set(self):
        """Set default option

        Normally this function is never called, which means that the config.txt file does not exist."""
        self.username = 'Me'
        self.others_name = 'Incognito'
        self.my_color = 'red'
        self.others_color = 'blue'

    def play_audio(self):
        """Based on the pseudo-random generated number, selects an audio file to be played"""
        self.media_player.setVolume(100)
        with open(f'audio/{self.rand_number}.wav', 'rb') as f:
            audio_data = f.read()
        asyncio.create_task(self.send_audio(audio_data))

    async def send_audio(self, file):
        """Send audio file that has been played"""
        self.writer.write(file)
        await self.writer.drain()

    def add_file_item(self, file_name: str):
        """Add item to the layout"""
        item = QStandardItem(file_name)
        item.setData(QColor('blue'), Qt.ForegroundRole)
        item.setEditable(False)
        self.model.appendRow(item)

    def my_keyPressEvent(self, event):
        """Re-defined keyPressEvent.
        In this case I add shift+enter key handler. When it's clicked user has had added the '\n' symbol

        NOTE, that in LineEdit widget in PyQt it visually simular to space symbol
        """
        if event.key() == Qt.Key_Return and event.modifiers() == Qt.ShiftModifier:
            self.line_edit.insert('\n')
        else:
            QLineEdit.keyPressEvent(self.line_edit, event)

    def clear_view_box(self):
        """This function start only when user click on the red pushbutton 'Clear'
        It just deletes all data from listview widget
        """
        self.model.clear()

    def _set_configuration(self) -> None:
        """Setting up starting options."""

        try:
            with open('config.txt', 'r', encoding='UTF-8') as config:
                content = config.readlines()
                for option in content:
                    if option.startswith('NAME='):
                        self.username = option[5:].strip()
                    elif option.startswith('YOUR_COLOR='):
                        self.my_color = option.split('=')[1].strip()
                    elif option.startswith('INCOGNITO_COLOR='):
                        self.others_color = option.split('=')[1].strip()
        except FileNotFoundError as fe:
            logging.error('Config.txt has gone. Set default options', exc_info=fe)
            self._default_set()

    def _safe_msg(self, text: str) -> None:
        """Checking the received ASCII message, if it's contain stop-word then start closing app """
        if re.fullmatch(r'\W*CATASTROPHE\W*', text, re.IGNORECASE):
            self.__close_app()

    async def send(self, text: str) -> None:
        if self.__is_key_alive():
            if text.strip():
                self.writer.write(text.encode())
                await self.writer.drain()

    async def send_file(self, file_path: str):
        """Asynch opening file and transferring"""
        async with aiofiles.open(file_path, 'rb', buffering=0) as file:
            res = await file.read()
        self.writer.write(res)
        await self.writer.drain()

    def get_clients_count_callback(self):
        asyncio.ensure_future(self.__get_clients_count())

    async def __get_clients_count(self):
        """Do request to the [host; port]/count server

        The response is a number - the current connection to the server"""
        async with aiohttp.ClientSession() as session:
            async with session.get('http://localhost:9999/count') as response:
                clients_count = await response.text()
                self.clients_count.setText(clients_count)

    def file_handler(self):
        """When FileUPload button has clicked it called this file_handler.
        File_handler open select window and wait until you choose or cancel,
        after it will asynchronously send file(if file was chosen)"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(self, 'Choose file', '')
            if file_path[0]:
                asyncio.create_task(self.send_file(file_path))
        except Exception:
            #  Do nothing when user changed his mind and clicked 'cancel' in opened window.
            pass

    async def write_file(self, save_path):
        async with aiofiles.open(save_path, 'wb') as f:
            await f.write(self._files[save_path])

    def on_list_view_double_clicked(self, index):
        item = self.model.itemFromIndex(index)
        file_name = item.text()
        try:
            save_path, _ = QFileDialog.getSaveFileName(self, 'Save file', file_name)
            if file_name and save_path:
                with open(save_path, 'wb') as f:
                    f.write(self._files['FILE'])
        except OSError:
            self.__close_app()
        except Exception:
            #  Do nothing when user changed his mind and clicked 'cancel' in opened window.
            pass

    def __is_key_alive(self) -> bool:
        """Scanning key field.
        There is three possible reactions:
            1. If key is correct, return True
            2. If key is not written (field empty) return False
            3. If key is written but it's incorrect return False and log it"""
        key = self.key_enter_box.text()
        if re.fullmatch(r'[^\s\w]{10}\w{10}', key, re.IGNORECASE):
            return True
        elif len(key) and re.match(r'.+', key):
            raise WrongKeyEntered
        logging.error('Key field empty')
        return False

    async def __wait_for_key(self) -> None:
        """Keep GUI window alive, but don't start important handler until key field is empty"""
        while not self.__is_key_alive():
            await asyncio.sleep(0.5)

    async def receive(self) -> None:
        """The main purpose of the method is to receive data that has been sent through the network and process it.
        This method do:
            1. Receiving data.
            2. Waiting for the key to decrypt data
            3. An attempt to decode the received data into a string and evaluate whether the data is empty or not.
            4. The message is broken into lines, and each line is processed with a QStandardItem and added to the queue.
            5. If data decoding fails, then the data type is determined and stored in  _files variable.

        NOTE, as GUI has circled angles I decide add some spaces from left side
        """
        while True:

            data = await self.reader.read(1024 * 1024 * 50)  # 50 MB
            while not self.__is_key_alive():
                await self.__wait_for_key()
            try:
                message = data
                if message.strip():
                    self._safe_msg(message.decode())
                    is_me = True if self.__last_sent_message is None or self.__last_sent_message.sender != 'Incognito' else False
                    sender, color = (self.username, self.my_color) if is_me else (self.others_name, self.others_color)
                    for idx, line in enumerate(message.splitlines()):
                        line = line.decode()
                        item = QStandardItem(f'{" " * 5}{sender}: ' + line if idx == 0 else line)
                        item.setData(QColor(f"{color}"), Qt.ForegroundRole)
                        item.setEditable(False)
                        self.queue.put_nowait(item)

                    self.__last_sent_message = self.sender_message('Incognito', message.decode())
            except UnicodeDecodeError:
                type_obj = self.magic_obj.from_buffer(data)
                if re.findall(r'audio|WAVE', type_obj, re.IGNORECASE):
                    path = os.path.join(os.getcwd(), f'audio/{self.rand_number}.wav')
                    self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(path)))
                    self.rand_number = random.randint(1, 6)
                    self.media_player.play()
                else:
                    self._files['FILE'] = data
                    self.add_file_item('FILE')
            except Exception as unk_err:
                logging.error('Unexpected error', exc_info=unk_err)
                raise

    async def start(self, app):
        """Connect to 'our' server and start some chatting

        """
        self._set_configuration()
        reader, writer = await asyncio.open_connection(host='localhost', port=7777)
        self.reader, self.writer = reader, writer

        asyncio.create_task(self.receive())
        self.timer.start()

        try:
            while True:
                app.processEvents()
                await asyncio.sleep(0.01)
                while not self.queue.empty():
                    item = await self.queue.get()
                    self.model.appendRow(item)
                    self.list_view.scrollToBottom()
                await asyncio.gather(*self._tasks)
        except OSError:
            self.__close_app()
        finally:
            self.__close_app()

    def write_message(self):
        """Scanning input message, send it to others.
        After scanning clearing LineEdit widget(our input message field)"""
        text: str = self.line_edit.text()
        if text.strip():
            self.line_edit.clear()
            self._tasks.append(asyncio.create_task(self.send(text=text)))
            self.__last_sent_message = self.sender_message(self.username, text)

    def __close_app(self, safe=True):
        """Final closing application"""
        self.timer.stop()

        clipboard = QApplication.clipboard()
        clipboard.clear()

        QApplication.processEvents()
        self.deleteLater()
        self.destroy()
        QApplication.quit()
        sys.exit(0 if safe else 1)


async def main():
    app = QtWidgets.QApplication(sys.argv)
    window = Ui()
    await window.start(app)


if __name__ == '__main__':
    asyncio.run(main())
