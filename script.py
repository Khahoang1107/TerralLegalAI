# -*- coding: utf-8 -*-
import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await context.new_page()
        
        print("Navigating to localhost:3000...")
        await page.goto("http://localhost:3000")
        
        print("Logging in...")
        await page.wait_for_selector('input[type="text"]')
        await page.fill('input[type="text"]', "admin@terralegal.vn")
        await page.fill('input[type="password"]', "admin123")
        await page.click('button:has-text("Đăng nhập")')
        
        print("Waiting for dashboard...")
        await page.wait_for_selector('text=Hệ thống')
        
        print("Clicking Người dùng...")
        await page.click('button:has-text("Người dùng")')
        
        print("Waiting for UsersView...")
        await page.wait_for_selector('text=Quản lý người dùng', timeout=10000)
        
        print("Taking screenshot...")
        await page.screenshot(path="C:/Users/ADMIN/.gemini/antigravity-ide/brain/e5653268-5d48-46d1-b902-77bcb9767cf4/users_view.png")
        
        await browser.close()
        print("Done!")

asyncio.run(run())
