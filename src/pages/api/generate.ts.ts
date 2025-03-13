import type { NextApiRequest, NextApiResponse } from 'next';
import axios from 'axios';
import cheerio from 'cheerio';

type RequestData = {
  url: string;
  depth: number;
};

type ResponseData = {
  success: boolean;
  data?: {
    llmsText: string;
    metadata: {
      crawlDate: string;
      sourceUrl: string;
    };
  };
  error?: string;
};

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse<ResponseData>
) {
  if (req.method !== 'POST') {
    return res.status(405).json({ success: false, error: 'Method not allowed' });
  }

  const { url, depth } = req.body as RequestData;

  try {
    // Fetch the webpage
    const response = await axios.get(url);
    const html = response.data;
    
    // Use markdowner to convert HTML to markdown
    // Note: This is a placeholder - you'll need to implement the actual markdowner integration
    const markdown = html; // Replace with actual conversion

    const llmsText = `# ${url}\n\n${markdown}`;
    
    return res.status(200).json({
      success: true,
      data: {
        llmsText,
        metadata: {
          crawlDate: new Date().toISOString(),
          sourceUrl: url,
        },
      },
    });
  } catch (error) {
    console.error('Error:', error);
    return res.status(500).json({
      success: false,
      error: 'Failed to generate LLMs.txt',
    });
  }
}