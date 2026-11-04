// Screenshots the seven visible pages of the Publish to web report, waiting for each page's visuals to finish drawing.
export default async function run(page, ui) {
  await page.setViewportSize({ width: 1920, height: 1160 })
  const out = []
  // Waits until the page has drawn: the canvas area stops changing between two checks a few seconds apart
  const settle = async (minMs) => {
    await page.waitForTimeout(minMs)
    let last = null
    for (let i = 0; i < 12; i++) {
      const buf = await page.screenshot({ clip: { x: 0, y: 0, width: 1920, height: 1080 } })
      if (last && buf.length === last.length) return
      last = buf
      await page.waitForTimeout(3000)
    }
  }
  for (let n = 1; n <= 7; n++) {
    await settle(n === 1 ? 20000 : 12000)
    const path = `${process.env.SHOT_DIR}/page${n}.png`
    await page.screenshot({ path })
    out.push(path)
    if (n < 7) await page.getByRole('button', { name: 'Next Page' }).click()
  }
  return out
}
