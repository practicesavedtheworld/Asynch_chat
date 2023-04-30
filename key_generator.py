import customtkinter
import tkinter as tk
import string
import random


class KeyGenerator:
    def __init__(self):
        self.generator = self.generate_key()

    def generate_new_key(self):
        return next(self.generator)

    @staticmethod
    def generate_key():
        while True:
            first_part = random.sample(string.punctuation.replace('_', ']'), k=10)
            second_part = random.sample(string.ascii_letters, k=10)
            yield ''.join(first_part + second_part).encode()


class App:
    def __init__(self, master):
        self.key_generator = KeyGenerator()

        self.master = master
        self.master.geometry('420x350')
        self.master.title('Secret Key Generator')

        self.key_label = customtkinter.CTkEntry(self.master, state='readonly', font=('Arial', 14), width=333)
        self.key_label.pack(pady=55)

        self.generate_button = customtkinter.CTkButton(self.master, text="Generate Key", font=('Arial', 14),
                                                       command=self.generate_key)
        self.generate_button.pack(pady=20)

        self.copy_button = None

    def generate_key(self):
        key = self.key_generator.generate_new_key()

        self.key_label.configure(state='normal')
        self.key_label.delete(0, tk.END)
        self.key_label.insert(tk.END, key)
        self.key_label.configure(state='readonly')

        if self.copy_button is None:
            self.copy_button = customtkinter.CTkButton(self.master, text="Copy Key", font=('Arial', 14))
            self.copy_button.pack(pady=10)
        self.copy_button.configure(command=lambda: self.copy_to_clipboard(key))

    def copy_to_clipboard(self, key):
        self.master.clipboard_clear()
        self.master.clipboard_append(key)


if __name__ == '__main__':
    customtkinter.set_appearance_mode('dark')
    root = customtkinter.CTk()
    app = App(root)
    root.mainloop()
