import tkinter as tk
import time
import math

def update_clock():
    current_time = time.localtime()
    seconds = current_time.tm_sec
    minutes = current_time.tm_min
    hours = current_time.tm_hour % 12

    # Calculate the angles for clock hands
    second_angle = (seconds / 60) * 360
    minute_angle = ((minutes + seconds / 60) / 60) * 360
    hour_angle = ((hours + minutes / 60) / 12) * 360

    # Clear canvas
    canvas.delete("all")

    # Draw clock face
    canvas.create_oval(50, 50, 250, 250)

    # Draw clock hands
    draw_hand(second_angle, 100, "red")
    draw_hand(minute_angle, 80, "blue")
    draw_hand(hour_angle, 60, "green")

    # Update every 1000 milliseconds (1 second)
    root.after(1000, update_clock)

def draw_hand(angle, length, color):
    radians = math.radians(angle - 90)  # Convert angle to radians
    x = 150 + length * math.cos(radians)
    y = 150 + length * math.sin(radians)
    canvas.create_line(150, 150, x, y, fill=color, width=2)

root = tk.Tk()
root.title("Analog Clock")

canvas = tk.Canvas(root, width=300, height=300)
canvas.pack()

update_clock()  # Start the clock update loop

root.mainloop()
