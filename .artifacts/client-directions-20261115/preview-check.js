async (page) => {
  const frame = page.frameLocator('iframe');
  const findings = [];
  for (const width of [1100, 768, 360]) {
    await page.setViewportSize({ width, height: 1200 });
    for (const direction of ['专注阅读', '协作工作台']) {
      const view = frame.getByRole('group', { name: direction, exact: true });
      if (!(await view.isVisible())) await frame.getByRole('button', { name: '下一种', exact: true }).click();
      for (const role of ['学生端', '教材助手']) {
        await view.getByRole('button', { name: role, exact: true }).click();
        const overflow = await view.locator('.dm-window:visible').evaluate(el => ({ scroll: el.scrollWidth, width: el.clientWidth }));
        if (overflow.scroll > overflow.width + 1) throw Error(JSON.stringify({ width, direction, role, overflow }));
        findings.push({ width, direction, role, overflow: false });
      }
      await view.getByRole('button', { name: '学生端', exact: true }).click();
      await view.getByRole('button', { name: '收起教材', exact: true }).click();
      if (await view.locator('.dm-book').isVisible()) throw Error('book did not collapse');
      await view.getByRole('button', { name: '展开教材', exact: true }).click();
      if (!(await view.locator('.dm-book').isVisible())) throw Error('book did not expand');
    }
  }
  await page.setViewportSize({ width: 1100, height: 1100 });
  await frame.getByRole('button', { name: '上一种', exact: true }).click();
  console.log(JSON.stringify(findings));
}
