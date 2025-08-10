=== FILE: stack.guidance.md ===
# Header Format
# path: <path>/<to>/<file.ext>
# desc: <short single sentence>
# api: <single public symbol>
# tags: <comma,separated,tags>

# Keys
path — unique merge key
desc — single short sentence
api — one public export
tags — for search/graph

# GLOBAL PRINCIPLES
1) One file, one job; one public symbol.
2) Small functions; flat control flow (nest ≤2); early returns.
3) No comments; intent lives in header + names.
4) Explicit types; stable return shapes; no hidden globals.
5) Absolute imports from app roots; no dynamic require/import.
6) Deterministic outputs; pass randomness/config explicitly.
7) Uniform layout: imports → types → constants → helpers → api.

=== SECTION: TypeScript (ts/tsx) ===
- Pure by default; ≤20 lines per function unless unavoidable.
- Data-first: inputs/outputs are plain objects.
- Never use `any` on public surfaces.
- Prefer tiny helpers over generic cleverness.

# Sample (utility)
// path: lib/normalize/toKebab.ts
// desc: Convert string to kebab-case
// api: toKebab
// tags: string,normalize
export type ToKebabInput = { value: string };
const SEP = /[^\p{L}\p{N}]+/u;
function _split(v: string){ return v.trim().split(SEP).filter(Boolean); }
export function toKebab(i: ToKebabInput){ return _split(i.value).map(s=>s.toLowerCase()).join("-"); }

=== SECTION: React Native UI (tsx) ===
- One component per file; default export.
- Presentational only; effects/data in small hooks.
- Props are flat + typed; avoid prop drilling (lift or store).
- Styles are constant objects; no inline objects in JSX.
- Platform-agnostic; gate rare platform bits via tiny adapters.
- Accessibility: set `accessibilityLabel` and testIDs.

# Sample (component)
// path: apps/reviewer/ItemRow.tsx
// desc: Pressable row with title/meta
// api: ItemRow
// tags: ui,reviewer,row
import React from "react";
import { Pressable, Text, View } from "react-native";
export type ItemRowProps = { title:string; meta?:string; onPress?:()=>void; testID?:string; };
export default function ItemRow(p: ItemRowProps){
  return (
    <Pressable onPress={p.onPress} accessibilityLabel={p.title} testID={p.testID}>
      <View style={S.row}><Text style={S.title}>{p.title}</Text>{p.meta ? <Text style={S.meta}>{p.meta}</Text> : null}</View>
    </Pressable>
  );
}
const S = {
  row:{ padding:12, gap:6, flexDirection:"column" } as const,
  title:{ fontSize:16, fontWeight:"600" } as const,
  meta:{ fontSize:12, opacity:0.7 } as const,
};

# Sample (hook)
// path: lib/hooks/usePaginatedList.ts
// desc: Load items page-by-page
// api: usePaginatedList
// tags: hooks,data
import { useEffect,useMemo,useState } from "react";
export type Page<T> = { items:T[]; next?:string };
export type Loader<T,P extends object=object> = (a:P & {cursor?:string})=>Promise<Page<T>>;
export function usePaginatedList<T,P extends object=object>(load:Loader<T,P>, params:P){
  const [items,setItems]=useState<T[]>([]); const [cursor,setCursor]=useState<string|undefined>(); const [busy,setBusy]=useState(false);
  const canLoadMore = useMemo(()=>!!cursor || items.length===0,[cursor,items.length]);
  async function loadMore(){ if(busy||!canLoadMore) return; setBusy(true); const p=await load({...params,cursor}); setItems(v=>v.concat(p.items)); setCursor(p.next); setBusy(false); }
  useEffect(()=>{ setItems([]); setCursor(undefined); },[JSON.stringify(params)]);
  return { items, loadMore, canLoadMore, busy };
}

=== SECTION: API Client (ts) ===
- One service per file; export a factory or typed function.
- Typed req/resp; do not return raw `Response`.
- Build URLs from base + path constants; JSON only.
- Never throw strings; return `{ ok, data? , error? }`.
- No implicit auth; pass token via options or store adapter.

# Sample (client)
// path: lib/api/reviewer.ts
// desc: Reviewer service client
// api: createReviewerClient
// tags: api,reviewer
export type ReviewerItem={ id:string; title:string; meta?:string };
export type ListArgs={ cursor?:string; limit?:number };
export type ListResult={ ok:true; data:{ items:ReviewerItem[]; next?:string } }|{ ok:false; error:{ code:string; message:string } };
export type Http=(url:string, init?:RequestInit)=>Promise<Response>;
const PATH={ list:"/api/reviewer/list" };
export function createReviewerClient(base:string, http:Http){
  async function list(a:ListArgs={}):Promise<ListResult>{
    const url=new URL(PATH.list,base); if(a.cursor) url.searchParams.set("cursor",a.cursor); if(a.limit!=null) url.searchParams.set("limit",String(a.limit));
    try{ const res=await http(url.toString(),{method:"GET"}); const payload=await res.json();
      return res.ok ? { ok:true, data:payload } : { ok:false, error:{ code:String(res.status), message:payload?.message??"Request failed" } };
    }catch(e){ return { ok:false, error:{ code:"NETWORK", message:(e as Error).message } }; }
  }
  return { list };
}

=== SECTION: JSON Manifest (apps/<module>/manifest.json) ===
- One manifest per module; strict + minimal; declarative only.
- Stable `id` (kebab-case); explicit `requires`/`provides`.
- Keep `ground_truth.md` next to the manifest.
- All referenced files must exist at build time.

# Minimal Schema (v1)
{
  "id":"reviewer",
  "name":"Reviewer",
  "entry":"index.tsx",
  "ground_truth":"ground_truth.md",
  "requires":["auth","user"],
  "provides":["reviewList","reviewEditor"],
  "schema_version":"1.0.0"
}
