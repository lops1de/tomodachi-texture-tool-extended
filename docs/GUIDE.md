# How to Use — Tomodachi Texture Tool

This guide shows you how to replace the texture of any custom item in **Tomodachi Life: Living the Dream** with your own PNG.

**Extended fork:** This version is built to **just work** end-to-end. When you **Convert & Export**, it writes every file the game expects — including **shop listing thumbnails** for item types that use them (everything except Facepaint). You should **not** need to open the in-game editor only to “fix” a broken shop icon. Use the **Browse / Export** tab to see what you already made, export PNGs, or use **Use for import** to jump back to **Import** with the same slot selected.

If your **Ugc** path is filled in automatically (common when using Ryujinx’s usual save layout), you can skip manually copying the folder path.

---

## Part 1 — Set up the tool

**Step 1 — Open Ryujinx and find your game**

Open Ryujinx and locate Tomodachi Life: Living the Dream.



---

**Step 2 — Open the save directory**

Right-click the game and select **Open User Save Directory**.



---

**Step 3 — Copy the Ugc folder path**

A folder will open. Navigate into the **Ugc** subfolder and copy its full path. *(If the tool already shows the correct **Ugc** path for you, you can keep that instead.)*



---

**Step 4 — Open the Tomodachi Texture Tool**

Launch the tool by double-clicking the exe.



---

**Step 5 — Paste the Ugc folder path**

Paste the path you copied into the **Ugc Folder** field.



---

**Step 6 — It should look like this**



---

**Step 7 — Select your item type and note the current highest ID**

Select the item type you want to replace. Pay close attention to the **highest** number shown — this is how many items of that type you currently have. You'll use this to verify the next steps went correctly.



---

## Part 2 — Create a placeholder item in-game

**Step 8 — Launch the game**

Start Tomodachi Life.



---

**Step 9 — Go to the Workshop**

Head to the **Workshop** building on your island.



---

**Step 10 — Select New Creation**

Click on **New Creation**.



---

**Step 11 — Choose your item category**

Pick the category that matches what you want to create. For this example we're going with **Treasures** (Goods).



---

**Step 12 — Choose the item type**

Select the specific type within the category. Here we choose **Pet**.



---

**Step 13 — Pick any design option**

It doesn't matter what you pick here — the texture will be replaced anyway. Choose **Free Design**.



---

**Step 14 — Draw a placeholder**

You can leave the canvas blank or scribble something — it doesn't matter, it will get replaced. For this tutorial we write **TTT** so it's easy to recognize.



---

**Step 15 — Give it a name**

Enter whatever name you want the item to have in-game.



---

**Step 16 — Choose grammatical options**

Just pick whatever fits. This is only for how the game refers to the item in text.



---

**Step 17 — Set the item properties**

Again, pick whatever you like here.



---

**Step 18 — Item created! Buy it right away**

Your item is now created. It's recommended to buy it immediately so it gets added to a Mii's inventory.



---

**Step 19 — Purchase confirmation**

Here we bought 2 copies as an example.



---

**Step 20 — Give the item to a Mii or place it**

Depending on what you created, either give it to a Mii or place it somewhere on the island.



---

**Step 21 — Looking good**



---

## Part 3 — Verify and convert

**Step 22 — Refresh so the new item shows up**

Go back to the Tomodachi Texture Tool. On **Browse / Export**, click **Refresh list** so the list and IDs are up to date. *(On the Import tab, switching to another item type and back also updates the highest-ID hint.)*



---

**Step 23 — Check the highest ID**

Select the **item type** you used in-game. The **highest** number should have gone up by 1 — for example from **002** to **003**. If it did, you’re on the right slot. **Save the game and close it before continuing — this is important!**



---

**Step 24 — Select your PNG**

Click the image box or **Browse PNG** and select the image you want to use as the texture.



---

**Step 25 — Set the Item ID**

Make sure the **Item ID** matches the highest number shown. Your image will appear as a preview.



---

**Step 26 — Convert & Export**

Click **Convert & Export**. When the green *Done* message appears, your **canvas** and **ugctex** files are saved. For types that use shop listings, the tool also writes the **thumbnail** (`…_Thumb.ugctex.zs`) so icons match your image — you should not need a separate in-game “fix” just for the listing picture. You can close the tool if you want.



---

## Part 4 — See it in-game

**Step 27 — Launch the game and go to Creations**

Start Tomodachi Life again and head to **Workshop → Creations**.



---

**Step 28 — Find the item you created**

Select the item from the list.



---

**Step 29 — Your texture should already appear**

Previews and lists (including shop-style screens, where that applies) should show your custom image. Use or place the item as usual — you do **not** need to open the editor first only to “apply” a texture you exported from this tool.



---

**Step 30 — (Optional) Open Change Design**

Use **Change Design** only if you want to **edit further** in the game’s drawing tools. If you’re happy with your PNG, you can skip this step entirely.



---

**Step 31 — Done!**

Your Mii can use the item with your custom texture. Have fun!



---

> The same flow works for every supported **item type** — match the **Item Type** in the tool to what you created in-game. Anytime, use **Browse / Export** to review or re-export textures from your save.