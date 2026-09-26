// Pixel serif lettering, 13px cap height. Thick stems are 3px, hairlines 1px,
// so the letters keep the thick/thin contrast of a carved Roman capital.
// In the O: "s" is the serpent (Ladon as an ouroboros), "e" its eye, "a" the apple it guards, "g" the stem.

const L = [
  "#######....",
  "..###......",
  "..###......",
  "..###......",
  "..###......",
  "..###......",
  "..###......",
  "..###......",
  "..###......",
  "..###.....#",
  "..###....##",
  "..###...###",
  "###########",
];

const A = [
  "......#......",
  ".....###.....",
  ".....###.....",
  "....#.###....",
  "....#.###....",
  "...#...###...",
  "...#...###...",
  "..#########..",
  "..#.....###..",
  ".#.......###.",
  ".#.......###.",
  "#.........###",
  "###.....#####",
];

const D = [
  "#########...",
  "..###...##..",
  "..###....##.",
  "..###.....##",
  "..###.....##",
  "..###.....##",
  "..###.....##",
  "..###.....##",
  "..###.....##",
  "..###.....##",
  "..###....##.",
  "..###...##..",
  "#########...",
];

const O = [
  "....sssss....",
  "..sssssss.s..",
  ".sss.....sse.",
  ".ss...g...ss.",
  "ss..aa.aa..ss",
  "ss..aaaaa..ss",
  "ss..aaaaa..ss",
  "ss...aaa...ss",
  "ss.........ss",
  ".ss.......ss.",
  ".sss.....sss.",
  "..sssssssss..",
  "....sssss....",
];

const N = [
  "###.......###",
  ".###.......#.",
  ".####......#.",
  ".#.###.....#.",
  ".#..###....#.",
  ".#...###...#.",
  ".#....###..#.",
  ".#.....###.#.",
  ".#......####.",
  ".#.......###.",
  ".#........##.",
  ".#.........#.",
  "###........#.",
];

const LETTERS = [L, A, D, O, N];
const GAP = 2;
const HEIGHT = 13;

type Run = { x: number; y: number; w: number; tone: string };

const TONES: Record<string, string> = {
  "#": "var(--color-marble)",
  s: "var(--color-dragon-light)",
  e: "var(--color-gold)",
  a: "var(--color-gold)",
  g: "var(--color-dragon)",
};

function toRuns(): { runs: Run[]; width: number } {
  const runs: Run[] = [];
  let offset = 0;
  for (const glyph of LETTERS) {
    glyph.forEach((row, y) => {
      let x = 0;
      while (x < row.length) {
        const tone = row[x];
        if (tone === ".") {
          x++;
          continue;
        }
        let end = x;
        while (end < row.length && row[end] === tone) end++;
        runs.push({ x: offset + x, y, w: end - x, tone });
        x = end;
      }
    });
    offset += glyph[0].length + GAP;
  }
  return { runs, width: offset - GAP };
}

const { runs, width } = toRuns();

export function Wordmark({ scale = 8, className = "" }: { scale?: number; className?: string }) {
  // The ink copy offset by one pixel is the drop shadow; a CSS filter would blur the pixels.
  return (
    <svg
      role="img"
      aria-label="Ladon"
      viewBox={`0 0 ${width + 1} ${HEIGHT + 1}`}
      width={(width + 1) * scale}
      height={(HEIGHT + 1) * scale}
      className={`pixel max-w-full h-auto ${className}`}
    >
      {runs.map((r, i) => (
        <rect key={`s${i}`} x={r.x + 1} y={r.y + 1} width={r.w} height={1} fill="var(--color-ink)" />
      ))}
      {runs.map((r, i) => (
        <rect key={i} x={r.x} y={r.y} width={r.w} height={1} fill={TONES[r.tone]} />
      ))}
    </svg>
  );
}
