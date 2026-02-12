import { useEffect, useRef, useState, useCallback, type ReactNode, type HTMLAttributes, type AnchorHTMLAttributes, type ImgHTMLAttributes, type TableHTMLAttributes, type TdHTMLAttributes, type ThHTMLAttributes } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import hljs from 'highlight.js/lib/core'
import python from 'highlight.js/lib/languages/python'
import javascript from 'highlight.js/lib/languages/javascript'
import typescript from 'highlight.js/lib/languages/typescript'
import sql from 'highlight.js/lib/languages/sql'
import bash from 'highlight.js/lib/languages/bash'
import json from 'highlight.js/lib/languages/json'
import xml from 'highlight.js/lib/languages/xml'

hljs.registerLanguage('python', python)
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('sql', sql)
hljs.registerLanguage('bash', bash)
hljs.registerLanguage('json', json)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('html', xml)

export function HighlightedCode({ code, language }: { code: string, language?: string }) {
  const codeRef = useRef<HTMLElement>(null)
  const highlightedRef = useRef(false)

  useEffect(() => {
    if (codeRef.current) {
      if (highlightedRef.current) {
        codeRef.current.removeAttribute('data-highlighted')
      }
      codeRef.current.textContent = code
      hljs.highlightElement(codeRef.current)
      highlightedRef.current = true
    }
  }, [code, language])

  return (
    <div className="rounded-md overflow-hidden border bg-[#282c34]">
      <div className="flex items-center justify-between px-3 py-1 bg-muted/80 text-xs text-muted-foreground font-mono border-b">
        <span>{language || 'code'}</span>
      </div>
      <pre className="p-3 overflow-x-auto">
        <code
          ref={codeRef}
          className={language ? `language-${language}` : ''}
        >
          {code}
        </code>
      </pre>
    </div>
  )
}

const MAX_IMG_RETRIES = 3
const RETRY_DELAYS = [500, 1000, 2000]

function RetryImage({ src, alt, ...rest }: ImgHTMLAttributes<HTMLImageElement>) {
  const [hidden, setHidden] = useState(false)
  const retryCount = useRef(0)
  const imgRef = useRef<HTMLImageElement>(null)

  const handleError = useCallback(() => {
    if (retryCount.current < MAX_IMG_RETRIES) {
      const delay = RETRY_DELAYS[retryCount.current] ?? 2000
      retryCount.current += 1
      setTimeout(() => {
        if (imgRef.current) {
          const sep = src?.includes('?') ? '&' : '?'
          imgRef.current.src = `${src}${sep}_retry=${retryCount.current}`
        }
      }, delay)
    } else {
      setHidden(true)
    }
  }, [src])

  if (hidden) return null

  return (
    <img
      ref={imgRef}
      src={src}
      alt={alt || 'Image'}
      className="max-w-full h-auto rounded border my-2"
      onError={handleError}
      {...rest}
    />
  )
}

type P = HTMLAttributes<HTMLElement>
type AP = AnchorHTMLAttributes<HTMLAnchorElement>
type IP = ImgHTMLAttributes<HTMLImageElement>
type TP = TableHTMLAttributes<HTMLTableElement>
type TDP = TdHTMLAttributes<HTMLTableCellElement>
type THP = ThHTMLAttributes<HTMLTableCellElement>

const mdComponents = {
  table: (props: TP) => (
    <div className="overflow-x-auto my-2">
      <table className="min-w-full border-collapse text-sm">{props.children}</table>
    </div>
  ),
  thead: (props: P) => <thead className="bg-muted">{props.children}</thead>,
  th: (props: THP) => <th className="border px-3 py-1.5 text-left font-semibold text-xs">{props.children}</th>,
  td: (props: TDP) => <td className="border px-3 py-1.5 text-xs">{props.children}</td>,
  tr: (props: P) => <tr className="even:bg-muted/50">{props.children}</tr>,
  pre: (props: P) => <div className="my-2">{props.children}</div>,
  code: (props: P & { className?: string }) => {
    const langMatch = props.className?.match(/language-(\w+)/)
    if (langMatch) {
      return <HighlightedCode code={extractTextContent(props.children)} language={langMatch[1]} />
    }
    return <code className="bg-muted px-1.5 py-0.5 rounded text-xs font-mono">{props.children}</code>
  },
  a: (props: AP) => (
    <a href={props.href} target="_blank" rel="noopener noreferrer" className="text-primary underline">
      {props.children}
    </a>
  ),
  ul: (props: P) => <ul className="list-disc pl-5 my-1 space-y-0.5">{props.children}</ul>,
  ol: (props: P) => <ol className="list-decimal pl-5 my-1 space-y-0.5">{props.children}</ol>,
  blockquote: (props: P) => (
    <blockquote className="border-l-4 border-primary/30 pl-3 my-2 text-muted-foreground italic">
      {props.children}
    </blockquote>
  ),
  h1: (props: P) => <h1 className="text-xl font-bold my-2">{props.children}</h1>,
  h2: (props: P) => <h2 className="text-lg font-bold my-2">{props.children}</h2>,
  h3: (props: P) => <h3 className="text-base font-semibold my-1.5">{props.children}</h3>,
  h4: (props: P) => <h4 className="text-sm font-semibold my-1">{props.children}</h4>,
  p: (props: P) => <p className="my-1">{props.children}</p>,
  img: (props: IP) => <RetryImage {...props} />,
}

export function MarkdownContent({ content, className }: { content: string, className?: string }) {
  return (
    <div className={`prose prose-sm max-w-none break-words ${className || ''}`}>
      <Markdown
        remarkPlugins={[remarkGfm]}
        urlTransform={(url: string) => url}
        components={mdComponents}
      >
        {content}
      </Markdown>
    </div>
  )
}

function extractTextContent(children: ReactNode): string {
  if (typeof children === 'string') return children
  if (Array.isArray(children)) return children.map(extractTextContent).join('')
  if (children && typeof children === 'object' && 'props' in children) {
    return extractTextContent((children as { props: { children?: ReactNode } }).props.children)
  }
  return String(children ?? '')
}
