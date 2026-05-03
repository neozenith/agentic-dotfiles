/**
 * Coverage matrix axes for the e2e suite.
 *
 * Add a route: append an entry to SECTIONS. Done.
 * Add an axis (locales, viewport sizes, auth states): copy the VARIANTS
 * shape and weave it into the MATRIX flatMap below.
 *
 * Slug format: S{id}_{SECTION}-V{id}_{VARIANT}
 * The numeric ids pad to two digits so 10+ entries still sort lexicographically.
 */

export const SECTIONS = [
	{ id: 0, slug: "home", name: "Home", path: "/" },
	{ id: 1, slug: "items", name: "Items", path: "/items" },
	{ id: 2, slug: "notes", name: "Notes", path: "/notes" },
] as const;

export const VARIANTS = [
	{ id: 0, slug: "default", name: "Default" },
] as const;

export type Section = (typeof SECTIONS)[number];
export type Variant = (typeof VARIANTS)[number];

const pad = (n: number): string => String(n).padStart(2, "0");

export const buildSlug = (section: Section, variant: Variant): string =>
	`S${pad(section.id)}_${section.slug.toUpperCase()}-V${pad(variant.id)}_${variant.slug.toUpperCase()}`;

export interface MatrixEntry {
	section: Section;
	variant: Variant;
	slug: string;
}

export const MATRIX: MatrixEntry[] = SECTIONS.flatMap((section) =>
	VARIANTS.map((variant) => ({
		section,
		variant,
		slug: buildSlug(section, variant),
	})),
);
