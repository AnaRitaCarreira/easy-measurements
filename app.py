import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
from PIL import Image, ImageTk
import cv2
import numpy as np
import json
import os
import csv
import sys

def resource_path(relative_path):
    """Resolve path para uso com PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)



class ImageMeasurementApp:
    def __init__(self, root):
        self.root = root
        icon_path = resource_path("./assets/logo.png")
        self.root.iconphoto(False, tk.PhotoImage(file=icon_path))
        self.root.title("Easy measurements")
        self.root.after(500, self.show_help_popup)
        #image = tk.PhotoImage(file=icon_path)

        self.root.bind("<Delete>", self.delete_selected_point)

        self.root.bind("<Control-z>", self.undo)
        self.root.bind("<Control-y>", self.redo)

        self.canvas = tk.Canvas(root, cursor="cross", bg="gray")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.cursor_pos = None
        self.canvas.bind("<Motion>", self.on_mouse_move)

        # Barra inferior com controle de zoom e opções
        control_frame = tk.Frame(root)
        control_frame.pack(fill=tk.X)

        self.zoom_slider = tk.Scale(control_frame, from_=10, to=800, orient=tk.HORIZONTAL, label="Zoom (%)", command=self.on_zoom_slider)
        self.zoom_slider.set(100)
        self.zoom_slider.pack(side=tk.LEFT, padx=5)

        tk.Button(control_frame, text="Resetar Zoom", command=self.reset_zoom).pack(side=tk.LEFT, padx=5)

        self.grid_var = tk.IntVar()
        tk.Checkbutton(control_frame, text="Mostrar Grade", variable=self.grid_var, command=self.toggle_grid).pack(side=tk.LEFT, padx=5)

        self.status = tk.Label(root, text="Carregue uma imagem para começar", anchor="w", relief="sunken")
        self.status.pack(fill=tk.X, side=tk.BOTTOM)


        self.selected_point_index = None
        self.dragging_point_index = None
        self.dragging = False
        self.setting_scale = False

        self.image = None
        self.tk_image = None
        self.display_image = None
        self.show_grid = False

        self.ref_points = []
        self.polygon_points = []
        self.pixels_per_cm = None
        self.mode = None
        self.set_mode(None)

        self.undo_stack = []
        self.redo_stack = []

        self.scale_factor = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.pan_start = None

        self.min_zoom = 0.1
        self.max_zoom = 8.0

        self.measure_label = tk.Label(root, text="", anchor="e", relief="sunken", font=("Arial", 10))
        self.measure_label.pack(fill=tk.X, side=tk.BOTTOM)   

        self.labels_var = tk.IntVar(value=1)
        tk.Checkbutton(control_frame, text="Mostrar labels", variable=self.labels_var, command=self.show_image).pack(side=tk.RIGHT, padx=5)   

        # Corrigir menu para compatibilidade com macOS
        menu_bar = tk.Menu(root)

        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="Abrir imagem", command=self.load_image)
        file_menu.add_command(label="Definir escala", command=self.set_scale_mode)
        file_menu.add_command(label="Medir polígono", command=self.set_polygon_mode)
        file_menu.add_separator()
        file_menu.add_command(label="⟲ Undo", command=self.undo)
        file_menu.add_command(label="⟳ Redo", command=self.redo)
        file_menu.add_command(label="Salvar imagem com medições", command=self.save_annotated_image)
        file_menu.add_command(label="Exportar medições CSV", command=self.export_measurements_csv)

        menu_bar.add_cascade(label="Arquivo", menu=file_menu)

        help_menu = tk.Menu(menu_bar, tearoff=0)
        help_menu.add_command(label="Mostrar ajuda", command=self.show_help_popup)
        menu_bar.add_cascade(label="Ajuda", menu=help_menu)

        root.config(menu=menu_bar)


        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<MouseWheel>", self.on_zoom)
        # PAN com botão esquerdo direto (independente do modo)
        self.canvas.bind("<Shift-Button-1>", self.start_pan)
        self.canvas.bind("<Shift-B1-Motion>", self.on_pan)

    def show_help_popup(self):
        config = load_config()
        if config.get("show_help", True):  # Só mostra se não estiver desativado

            popup = tk.Toplevel(self.root)
            popup.title("Ajuda - Como usar")
            popup.geometry("500x350")
            popup.resizable(False, False)

            tk.Label(popup, text=(
                "➡ Abrir imagem: Menu > Abrir imagem\n"
                "➡ Definir escala: Menu > Definir escala, clique em dois pontos da régua\n"
                "➡ Medir área: Menu > Medir polígono, clique para formar o contorno, botão direito para fechar\n\n"
                "🖱 Zoom: Roda do rato ou controle na barra inferior\n"
                "↔ Pan: SHIFT + Clique esquerdo e arrastar\n"
                "🎛 Mostrar/ocultar grade: Caixa na barra inferior\n"
            ), justify="left", anchor="w", padx=10, pady=10).pack(fill="both", expand=True)

            var = tk.IntVar(value=1)
            chk = tk.Checkbutton(popup, text="Mostrar esta ajuda ao iniciar", variable=var)
            chk.pack(pady=(0, 10))

            def fechar():
                save_config({"show_help": bool(var.get())})
                popup.destroy()

            tk.Button(popup, text="Fechar", command=fechar).pack(pady=(0, 10))


    import sys
    import os

    def resource_path(relative_path):
        """ Resolve path para data no PyInstaller """
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, relative_path)
        return os.path.join(os.path.abspath("."), relative_path)

    def on_mouse_move(self, event):
        if self.image is None or self.display_image is None:
            self.canvas.config(cursor="arrow")
            return

        self.cursor_pos = (event.x, event.y)
        self.show_image()
        # Verifica se o rato está sobre a imagem
        if 0 <= event.x < self.display_image.shape[1] and 0 <= event.y < self.display_image.shape[0]:
            if self.setting_scale:
                self.canvas.config(cursor="hand2")
            else:
                self.canvas.config(cursor="crosshair")
        else:
            self.canvas.config(cursor="arrow")

    def on_mouse_down(self, event):
        if self.image is None:
            return

        self.canvas.config(cursor="circle")  # opcional

        x, y = event.x, event.y
        if self.setting_scale:
            self.scale_points.append((x, y))
            if len(self.scale_points) == 2:
                self.set_scale()
        else:
            self.polygon_points.append((x, y))
            self.draw_image()

    def on_mouse_up(self, event):
        self.on_mouse_move(event)  # reavalia o cursor com base na posição e modo




    def load_image(self):
        file_path = filedialog.askopenfilename()
        if file_path:
            self.image = cv2.cvtColor(cv2.imread(file_path), cv2.COLOR_BGR2RGB)
            max_width = 1200
            max_height = 800

            h, w = self.image.shape[:2]
            scaling = min(max_width / w, max_height / h, 1.0)

            if scaling < 1.0:
                self.image = cv2.resize(
                    self.image, (int(w * scaling), int(h * scaling)), interpolation=cv2.INTER_AREA
                )
            self.display_image = self.image.copy()
            self.scale_factor = 1.0
            self.pixels_per_cm = None
            self.offset_x = 0
            self.offset_y = 0
            self.show_image()
        self.update_status("Imagem carregada. Use Shift + Clique Esquerdo para mover (Pan).")


    def update_status(self, message):
        self.status.config(text=message)

    def toggle_grid(self):
        self.show_grid = bool(self.grid_var.get())
        self.show_image()

    def show_image(self):
        if self.image is None:
            return

        img = cv2.resize(
            self.display_image,
            None,
            fx=self.scale_factor,
            fy=self.scale_factor,
            interpolation=cv2.INTER_LINEAR,
        )
        img = Image.fromarray(img)
        self.tk_image = ImageTk.PhotoImage(img)

        self.canvas.delete("all")
        self.canvas.create_image(self.offset_x, self.offset_y, anchor=tk.NW, image=self.tk_image)

        # Desenhar grade
        if self.show_grid:
            spacing = 50
            img_h, img_w = self.image.shape[:2]
            for x in range(0, img_w, spacing):
                x_disp = x * self.scale_factor + self.offset_x
                self.canvas.create_line(x_disp, 0, x_disp, self.canvas.winfo_height(), fill="gray")
            for y in range(0, img_h, spacing):
                y_disp = y * self.scale_factor + self.offset_y
                self.canvas.create_line(0, y_disp, self.canvas.winfo_width(), y_disp, fill="gray")

        # Desenhar pontos e linhas do polígono
        for i, (x, y) in enumerate(self.polygon_points):
            x_disp = int(x * self.scale_factor + self.offset_x)
            y_disp = int(y * self.scale_factor + self.offset_y)
            color = "red" if i == self.selected_point_index else "blue"
            self.canvas.create_oval(x_disp - 4, y_disp - 4, x_disp + 4, y_disp + 4, fill=color)

            # Desenhar linhas + rótulos
            if len(self.polygon_points) > 1:
                for i in range(len(self.polygon_points) - 1):
                    x1, y1 = self.polygon_points[i]
                    x2, y2 = self.polygon_points[i + 1]

                    sx1 = x1 * self.scale_factor + self.offset_x
                    sy1 = y1 * self.scale_factor + self.offset_y
                    sx2 = x2 * self.scale_factor + self.offset_x
                    sy2 = y2 * self.scale_factor + self.offset_y

                    self.canvas.create_line(sx1, sy1, sx2, sy2, fill="blue", width=2)
                    # comprimento da linha
                    dist_px = np.linalg.norm(np.array([x2, y2]) - np.array([x1, y1]))
                    if self.pixels_per_cm:
                        dist_cm = dist_px / self.pixels_per_cm
                        label = f"{dist_cm:.2f} cm"
                    else:
                        label = f"{dist_px:.1f} px"

                    if self.labels_var.get():
                        length_px = np.hypot(x2 - x1, y2 - y1)
                        if self.pixels_per_cm:
                            length_cm = length_px / self.pixels_per_cm
                            text = f"{length_cm:.2f} cm"
                        else:
                            text = f"{length_px:.0f} px"

                        # posição central da linha
                        mx = (sx1 + sx2) / 2
                        my = (sy1 + sy2) / 2

                        # desenhar balão (caixa de texto com fundo)
                        padding = 4
                        text_id = self.canvas.create_text(mx, my, text=label, font=("Arial", 10), anchor="c")
                        bbox = self.canvas.bbox(text_id)
                        if bbox:
                            x0, y0, x1, y1 = bbox
                            self.canvas.create_rectangle(x0 - padding, y0 - padding, x1 + padding, y1 + padding,
                                                        fill="white", outline="black", width=1)
                            # redesenha o texto para cima da caixa
                            self.canvas.lift(text_id)

            self.calculate_area_and_perimeter()


        # Linha do último ponto até o cursor (preview)
        if self.mode == "polygon" and self.cursor_pos and len(self.polygon_points) > 0:
            x_last, y_last = self.polygon_points[-1]
            x1_disp = x_last * self.scale_factor + self.offset_x
            y1_disp = y_last * self.scale_factor + self.offset_y
            x2_disp, y2_disp = self.cursor_pos
            self.canvas.create_line(
                x1_disp, y1_disp, x2_disp, y2_disp,
                fill="lightblue", dash=(4, 2), width=2
            )

        # Mostrar linha sketch no modo escala
        if self.mode == "scale" and self.cursor_pos and len(self.ref_points) == 1:
            x1, y1 = self.ref_points[0]
            x1_disp = x1 * self.scale_factor + self.offset_x
            y1_disp = y1 * self.scale_factor + self.offset_y
            x2_disp, y2_disp = self.cursor_pos
            self.canvas.create_line(
                x1_disp, y1_disp, x2_disp, y2_disp,
                fill="orange", dash=(4, 2), width=2
            )

        # Pontos de escala
        if self.mode == "scale":
            for x, y in self.ref_points:
                x_disp = int(x * self.scale_factor + self.offset_x)
                y_disp = int(y * self.scale_factor + self.offset_y)
                self.canvas.create_oval(x_disp - 4, y_disp - 4, x_disp + 4, y_disp + 4, fill="orange")

        self.root.title("Medidor com Zoom e Pan - Zoom: {:.0f}%".format(self.scale_factor * 100))


    def activate_scale_mode(self):
        self.setting_scale = True
        self.polygon_points.clear()
        self.scale_points.clear()
        self.canvas.config(cursor="hand2")

    def activate_measure_mode(self):
        self.setting_scale = False
        self.scale_points.clear()
        self.canvas.config(cursor="crosshair")


    def save_annotated_image(self):
        if self.image is None:
            messagebox.showwarning("Aviso", "Nenhuma imagem carregada.")
            return

        # Cria uma cópia da imagem original para desenhar
        img_copy = self.image.copy()

        # Desenha as linhas e pontos
        for i in range(len(self.polygon_points) - 1):
            x1, y1 = self.polygon_points[i]
            x2, y2 = self.polygon_points[i + 1]

            cv2.line(img_copy, (x1, y1), (x2, y2), (0, 0, 255), 2)  # vermelho

            # Texto com medida
            mid_x = int((x1 + x2) / 2)
            mid_y = int((y1 + y2) / 2)
            dist_px = np.linalg.norm(np.array([x2, y2]) - np.array([x1, y1]))

            if self.pixels_per_cm:
                text = f"{dist_px / self.pixels_per_cm:.2f} cm"
            else:
                text = f"{dist_px:.0f} px"

            cv2.putText(img_copy, text, (mid_x, mid_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # Salvar imagem
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG Image", "*.png")])
        if path:
            cv2.imwrite(path, cv2.cvtColor(img_copy, cv2.COLOR_RGB2BGR))
            messagebox.showinfo("Salvo", f"Imagem salva em:\n{path}")



    def export_measurements_csv(self):
        if not self.polygon_points:
            messagebox.showwarning("Aviso", "Nenhum polígono definido.")
            return

        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV file", "*.csv")])
        if not path:
            return

        with open(path, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Segmento", "Ponto Inicial", "Ponto Final", "Distância"])

            total_length = 0
            for i in range(len(self.polygon_points) - 1):
                x1, y1 = self.polygon_points[i]
                x2, y2 = self.polygon_points[i + 1]
                dist_px = np.linalg.norm(np.array([x2, y2]) - np.array([x1, y1]))
                if self.pixels_per_cm:
                    dist = dist_px / self.pixels_per_cm
                    unidade = "cm"
                else:
                    dist = dist_px
                    unidade = "px"
                writer.writerow([
                    i + 1,
                    f"({x1}, {y1})",
                    f"({x2}, {y2})",
                    f"{dist:.2f} {unidade}"
                ])
                total_length += dist

            # Área e perímetro
            area = self.calculate_area_raw()
            area_str = f"{area / (self.pixels_per_cm ** 2):.2f} cm²" if self.pixels_per_cm else f"{area:.2f} px²"
            perimeter_str = f"{total_length:.2f} {unidade}"

            writer.writerow([])
            writer.writerow(["Perímetro total", perimeter_str])
            writer.writerow(["Área do polígono", area_str])

        messagebox.showinfo("Salvo", f"Medições exportadas para:\n{path}")

    def calculate_area_raw(self):
        pts = self.polygon_points
        if len(pts) < 3:
            return 0
        pts = np.array(pts)
        area = 0
        for i in range(len(pts)):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % len(pts)]
            area += x1 * y2 - x2 * y1
        return abs(area) / 2.0


    def set_scale_mode(self):
        self.mode = "scale"
        self.set_mode("scale")
        #print("MODO ESCALA")
        self.ref_points = []
        self.update_status("Modo: clique em 2 pontos sobre a régua para definir quantos pixels equivalem a 1 cm.")

    def set_polygon_mode(self):
        self.mode = "polygon"
        self.set_mode(self.mode)
        self.polygon_points = []
        self.display_image = self.image.copy()
        self.show_image()
        self.update_status("Modo: clique nos vértices do polígono; botão direito para fechar. (Pan: Shift + Clique Esquerdo)")

    def canvas_to_image_coords(self, x, y):
        ix = (x - self.offset_x) / self.scale_factor
        iy = (y - self.offset_y) / self.scale_factor
        return int(ix), int(iy)

    def on_click(self, event):
        x, y = self.canvas_to_image_coords(event.x, event.y)

        if self.mode == "scale":
            self.ref_points.append((x, y))
            if len(self.ref_points) == 2:
                p1, p2 = self.ref_points
                dist = np.linalg.norm(np.array(p1) - np.array(p2))
                self.pixels_per_cm = dist
                self.update_status(f"Escala definida: {dist:.2f} pixels = 1 cm")
            self.show_image()
        
        else:
        #elif self.mode == "polygon":
            # Verifica se clicou perto de um ponto
            for i, (px, py) in enumerate(self.polygon_points):
                if np.hypot(x - px, y - py) < 8:
                    self.dragging_point_index = i
                    self.selected_point_index = i
                    self.dragging = True
                    self.update_status("Para apagar este ponto - Delete; Para mover, arraste-o.")
                    return
            # Inserir ponto no meio de uma linha
            insert_threshold = 8  # pixels

            for i in range(len(self.polygon_points) - 1):
                x1, y1 = self.polygon_points[i]
                x2, y2 = self.polygon_points[i + 1]

                # Converter coordenadas para o espaço do canvas
                sx1 = x1 * self.scale_factor + self.offset_x
                sy1 = y1 * self.scale_factor + self.offset_y
                sx2 = x2 * self.scale_factor + self.offset_x
                sy2 = y2 * self.scale_factor + self.offset_y

                # Distância ponto-linha
                px, py = event.x, event.y
                dist = self.point_to_segment_distance(px, py, sx1, sy1, sx2, sy2)

                if dist < insert_threshold:
                    # Coordenadas no espaço da imagem
                    new_x, new_y = self.canvas_to_image_coords(event.x, event.y)
                    self.save_state()
                    self.polygon_points.insert(i + 1, (new_x, new_y))
                    self.update_measurements()
                    self.show_image()
                    return
            # Caso contrário, adiciona novo ponto
            self.save_state()
            self.polygon_points.append((x, y))
            self.selected_point_index = None
            self.dragging_point_index = None
            self.update_measurements()
            self.show_image()
            #print("x,y:", x, y)

    def point_to_segment_distance(self, px, py, x1, y1, x2, y2):
        # Distância mínima de ponto (px, py) ao segmento (x1,y1)-(x2,y2)
        line_mag = np.hypot(x2 - x1, y2 - y1)
        if line_mag < 1e-6:
            return np.hypot(px - x1, py - y1)

        u = ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / (line_mag ** 2)
        u = max(min(u, 1), 0)  # clamp entre 0 e 1
        ix = x1 + u * (x2 - x1)
        iy = y1 + u * (y2 - y1)
        return np.hypot(px - ix, py - iy)

    def on_right_click(self, event):
        if self.mode == "polygon" and len(self.polygon_points) > 2:
            self.polygon_points.append(self.polygon_points[0])  # fecha o polígono
            self.show_image()
            #self.calculate_area_and_perimeter()
            self.cursor_pos = None
            #print("Botão direito")
            # Sai do modo desenho
            self.mode = None
            self.update_status("Desenho finalizado. Clique em 'Medir polígono' para começar outro.")

    def delete_selected_point(self, event=None):
        if self.selected_point_index is not None:
            self.save_state()
            del self.polygon_points[self.selected_point_index]
            self.selected_point_index = None
            self.update_measurements()
            self.show_image()

    def save_state(self):
        self.undo_stack.append(list(self.polygon_points))
        self.redo_stack.clear()  # limpa redo ao fazer nova ação

    def on_motion(self, event):
        if self.dragging and self.dragging_point_index is not None:
            x, y = self.canvas_to_image_coords(event.x, event.y)
            self.polygon_points[self.dragging_point_index] = (x, y)
            self.update_measurements()
            self.show_image()

    def on_release(self, event):
            self.dragging = False
            self.dragging_point_index = None

    def undo(self, event=None):
        if self.undo_stack:
            self.redo_stack.append(list(self.polygon_points))
            self.polygon_points = self.undo_stack.pop()
            self.update_measurements()
            self.show_image()

    def redo(self, event=None):
        if self.redo_stack:
            self.undo_stack.append(list(self.polygon_points))
            self.polygon_points = self.redo_stack.pop()
            self.update_measurements()
            self.show_image()

    def update_measurements(self):
        self.calculate_area_and_perimeter()

    def calculate_area_and_perimeter(self):
        
        pts = self.polygon_points
        n = len(pts)
        pts = np.array(self.polygon_points)
        if n < 2:
            # Só 0 ou 1 ponto, perímetro e área = 0
            area = 0
            perimeter = 0
        if n < 3:
            perimeter = 0
            for i in range(n - 1):
                perimeter += np.linalg.norm(np.array(pts[i + 1]) - np.array(pts[i]))

            
                # Com menos de 3 pontos, área = 0 (não fecha o polígono)
                area = 0
        if n >= 3:
            # Se tem 3+ pontos, fecha o polígono para perímetro e calcula área
            perimeter = 0
            for i in range(n - 1):
                perimeter += np.linalg.norm(np.array(pts[i + 1]) - np.array(pts[i]))

            # Área pelo método do polígono (shoelace)
            area = 0
            for i in range(n):
                x1, y1 = pts[i]
                x2, y2 = pts[(i + 1) % n]
                area += x1 * y2 - x2 * y1
            area = abs(area) / 2.0

        
        if self.pixels_per_cm:
            area_cm2 = area / (self.pixels_per_cm ** 2)
            perimeter_cm = perimeter / self.pixels_per_cm
            self.update_status(f"Área: {area_cm2:.2f} cm²   |   Perímetro: {perimeter_cm:.2f} cm")
            self.measure_label.config(text=f"Área: {area_cm2:.2f} cm²   |   Perímetro: {perimeter_cm:.2f} cm")
        else:
            self.update_status("Defina a escala primeiro!")
            self.measure_label.config(text="Escala não definida.")


    def update_cursor(self):
        if self.mode == "polygon":
            self.canvas.config(cursor="crosshair")  # para desenho
        elif self.mode == "pan":
            self.canvas.config(cursor="fleur")      # cursor de pan
        elif self.mode == "scale":
            self.canvas.config(cursor="tcross")     # para definir escala
        else:
            self.canvas.config(cursor="arrow")      # modo padrão

    def set_mode(self, new_mode):
        self.mode = new_mode
        self.update_cursor()

    def on_zoom(self, event):
        # Zoom in/out (wheel up/down)
        factor = 1.1 if event.delta > 0 else 0.9
        new_scale = self.scale_factor * factor

        # Limites
        if new_scale < self.min_zoom or new_scale > self.max_zoom:
            return

        # Coordenadas do cursor no canvas
        mouse_x, mouse_y = event.x, event.y

        # Ponto da imagem sob o cursor (antes do zoom)
        ix = (mouse_x - self.offset_x) / self.scale_factor
        iy = (mouse_y - self.offset_y) / self.scale_factor

        # Aplicar novo zoom
        self.scale_factor = new_scale

        # Atualizar offset para manter foco no ponto original
        self.offset_x = mouse_x - ix * self.scale_factor
        self.offset_y = mouse_y - iy * self.scale_factor

        self.show_image()

    def on_zoom_slider(self, val):
        new_scale = int(val) / 100.0
        # manter centro da tela fixo
        canvas_center_x = self.canvas.winfo_width() / 2
        canvas_center_y = self.canvas.winfo_height() / 2

        ix = (canvas_center_x - self.offset_x) / self.scale_factor
        iy = (canvas_center_y - self.offset_y) / self.scale_factor

        self.scale_factor = new_scale
        self.offset_x = canvas_center_x - ix * self.scale_factor
        self.offset_y = canvas_center_y - iy * self.scale_factor
        self.show_image()

    def start_pan(self, event):
        self.pan_start = (event.x, event.y)
        self.mode = "pan"
        self.set_mode(self.mode)

    def on_pan(self, event):
        if self.pan_start:
            dx = event.x - self.pan_start[0]
            dy = event.y - self.pan_start[1]
            self.offset_x += dx
            self.offset_y += dy
            self.pan_start = (event.x, event.y)
            self.show_image()

    def reset_zoom(self):
        self.scale_factor = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.zoom_slider.set(100)
        self.show_image()
        self.update_status("Zoom redefinido para 100%. Use Shift + Clique Esquerdo para mover (Pan).")


CONFIG_FILE = "config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f)


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1280x900")  # Tamanho inicial da janela
    app = ImageMeasurementApp(root)
    root.mainloop()