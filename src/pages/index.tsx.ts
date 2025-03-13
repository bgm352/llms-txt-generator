import { useState } from 'react';
import Head from 'next/head';

export default function Home() {
  const [url, setUrl] = useState('');
  const [depth, setDepth] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [preview, setPreview] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      const response = await fetch('/api/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ url, depth }),
      });
      const data = await response.json();
      setPreview(data.data.llmsText);
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100">
      <Head>
        <title>LLMs.txt Generator</title>
        <meta name="description" content="Generate LLMs.txt files from websites" />
        <link rel="icon" href="/favicon.ico" />
      </Head>

      <main className="container mx-auto px-4 py-8">
        <h1 className="text-4xl font-bold text-center mb-8">
          LLMs.txt Generator
        </h1>

        <form onSubmit={handleSubmit} className="max-w-xl mx-auto space-y-4">
          <div>
            <label htmlFor="url" className="block text-sm font-medium text-gray-700">
              Website URL
            </label>
            <input
              type="url"
              id="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
              required
            />
          </div>

          <div>
            <label htmlFor="depth" className="block text-sm font-medium text-gray-700">
              Crawl Depth
            </label>
            <input
              type="number"
              id="depth"
              value={depth}
              onChange={(e) => setDepth(parseInt(e.target.value))}
              min="1"
              max="10"
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
          >
            {isLoading ? 'Generating...' : 'Generate LLMs.txt'}
          </button>
        </form>

        {preview && (
          <div className="mt-8 max-w-xl mx-auto">
            <h2 className="text-2xl font-bold mb-4">Preview</h2>
            <pre className="bg-white p-4 rounded-md shadow overflow-auto">
              {preview}
            </pre>
          </div>
        )}
      </main>
    </div>
  );
}