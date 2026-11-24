// Guided views use the same clock, camera and layer switches as free exploration.
export const STORIES = [
  {
    id: 'daylight',
    title: 'Where is it daylight?',
    subject: 'Sun & orbit',
    summary: 'Follow the line between day and night.',
    detail: 'The day–night boundary crosses cities and oceans as Earth turns. Watch the estimate of people in daylight change with it.',
    view: { style: 'space', lens: 'none', layers: { daylight: true, lights: true } },
  },
  {
    id: 'seasons',
    title: 'June vs. December',
    subject: 'Oceans & seasons',
    summary: 'Compare sunlight and sea ice near the solstices.',
    detail: 'Switch months at the same scale. Each pole gains daylight while the other loses it, and sea ice follows its own seasonal cycle.',
    view: { style: 'atlas', lens: 'ice', layers: { daylight: false, clouds: false, ice: true } },
  },
  {
    id: 'plates',
    title: 'The Pacific Ring of Fire',
    subject: 'Solid Earth',
    summary: 'Trace the Pacific’s active plate edges.',
    detail: 'Follow the plate edges across the sea-floor relief. Select an earthquake for its magnitude, depth and date.',
    view: { style: 'space', lens: 'elev', layers: { clouds: false, lights: false, plates: true, volcanoes: true, quakesLive: true } },
  },
];

export const STORY_BY_ID = Object.fromEntries(STORIES.map((story) => [story.id, story]));
