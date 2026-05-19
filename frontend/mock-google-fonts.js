// mock-google-fonts.js — offline mock for NEXT_FONT_GOOGLE_MOCKED_RESPONSES
// Serves font files from previous build output via absolute paths.

const path = require('path');

const MEDIA_DIR = path.resolve(__dirname, 'out/_next/static/media');

// Inter @font-face subsets (from previous build CSS)
const INTER_SUBSETS = [
  ['2c55a0e60120577a-s.2a48534a.woff2', 'U+460-52F, U+1C80-1C8A, U+20B4, U+2DE0-2DFF, U+A640-A69F, U+FE2E-FE2F'],
  ['9c72aa0f40e4eef8-s.18a48cbc.woff2', 'U+301, U+400-45F, U+490-491, U+4B0-4B1, U+2116'],
  ['ad66f9afd8947f86-s.7a40eb73.woff2', 'U+1F00-1FFF'],
  ['5476f68d60460930-s.c995e352.woff2', 'U+370-377, U+37A-37F, U+384-38A, U+38C, U+38E-3A1, U+3A3-3FF'],
  ['2bbe8d2671613f1f-s.76dcb0b2.woff2', 'U+102-103, U+110-111, U+128-129, U+168-169, U+1A0-1A1, U+1AF-1B0, U+300-301, U+303-304, U+308-309, U+323, U+329, U+1EA0-1EF9, U+20AB'],
  ['1bffadaabf893a1e-s.7cd81963.woff2', 'U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD'],
  ['3fe682a82f50d426-s.23358719.woff2', 'U+0100-02AF, U+0304, U+0308, U+0329, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C0, U+2113, U+2C60-2C7F, U+A720-A7FF'],
  ['71b036adf157cdcf-s.bd5f4d11.woff2', 'U+0100-02AF, U+0304, U+0308, U+0329, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C0, U+2113, U+2C60-2C7F, U+A720-A7FF'],
  ['89b21bb081cb7469-s.51c18f09.woff2', 'U+0100-02AF, U+0304, U+0308, U+0329, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C0, U+2113, U+2C60-2C7F, U+A720-A7FF'],
  ['70bc3e132a0a741e-s.p.15008bfb.woff2', 'U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD'],
  ['83afe278b6a6bb3c-s.p.3a6ba036.woff2', 'U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD'],
];

const JBM_SUBSETS = [
  ['13bf9871fe164e7f-s.f2220059.woff2', 'U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD'],
  ['cc545e633e20c56d-s.f6f1950f.woff2', 'U+0100-02AF, U+0304, U+0308, U+0329, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C0, U+2113, U+2C60-2C7F, U+A720-A7FF'],
];

function buildCss(fontFamily, weightRange, subsets) {
  const faces = subsets.map(([file, range]) => {
    const absPath = path.join(MEDIA_DIR, file);
    return `/* ${range.split(',')[0].trim()} */\n@font-face{\nfont-family:${fontFamily};\nfont-style:normal;\nfont-weight:${weightRange};\nfont-display:swap;\nsrc:url(${absPath}) format('woff2');\nunicode-range:${range};\n}`;
  });
  return faces.join('\n');
}

const interCss = buildCss('Inter', '100 900', INTER_SUBSETS);
const jbmCss = buildCss('JetBrains Mono', '100 800', JBM_SUBSETS);

// The URL keys must match what Next.js generates internally.
// Next.js /v2/ format: family=Name:wght@min..max
module.exports = {
  'https://fonts.googleapis.com/css2?family=Inter:wght@100..900&display=swap': interCss,
  'https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@100..800&display=swap': jbmCss,
  // Also handle the exact format Next.js v15 generates (with @ min..max)
  'https://fonts.googleapis.com/css2?family=Inter:wght@100%20900&display=swap': interCss,
  'https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@100%20800&display=swap': jbmCss,
};
