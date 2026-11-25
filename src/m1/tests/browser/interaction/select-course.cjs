const assert = require('node:assert/strict');

async function enterCourse(page, title) {
  await page.getByRole('button', { name: /^(选择|切换)学习空间$/ }).click();
  const picker = page.getByRole('dialog', { name: '切换学习空间' });
  const match = picker.getByRole('listitem').filter({ hasText: title });
  const current = picker.locator('[aria-current="true"]').filter({ hasText: title });
  await current.or(match).first().waitFor();
  if (await current.count()) {
    await page.keyboard.press('Escape');
  } else {
    await match
      .first()
      .getByRole('button', { name: /^(创建|进入)空间 / })
      .click();
  }
  await picker.waitFor({ state: 'hidden' });
  const scope = new URL(page.url()).searchParams.get('space');
  assert.ok(scope, '学习空间已打开并写入地址');
  return scope;
}

module.exports = { enterCourse };
