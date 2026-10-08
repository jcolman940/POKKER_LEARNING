# Generates src\launcher\pokker.ico: dark green rounded square with a white "P",
# 16/32/48 px, 32-bit BMP (DIB) entries so csc /win32icon and every Windows shell accept it.
# Usage (from the repo root): powershell -ExecutionPolicy Bypass -File src\launcher\make-icon.ps1
param([string]$Out = (Join-Path $PSScriptRoot 'pokker.ico'))
$ErrorActionPreference = 'Stop'

Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Text;
using System.IO;

public static class PokkerIcon
{
    static Bitmap Draw(int size)
    {
        var bmp = new Bitmap(size, size, System.Drawing.Imaging.PixelFormat.Format32bppArgb);
        using (var g = Graphics.FromImage(bmp))
        {
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.TextRenderingHint = TextRenderingHint.AntiAliasGridFit;
            g.Clear(Color.Transparent);
            float r = size / 5f;
            var path = new GraphicsPath();
            path.AddArc(0, 0, r * 2, r * 2, 180, 90);
            path.AddArc(size - 1 - r * 2, 0, r * 2, r * 2, 270, 90);
            path.AddArc(size - 1 - r * 2, size - 1 - r * 2, r * 2, r * 2, 0, 90);
            path.AddArc(0, size - 1 - r * 2, r * 2, r * 2, 90, 90);
            path.CloseFigure();
            using (var fill = new SolidBrush(Color.FromArgb(255, 18, 92, 52)))
            {
                g.FillPath(fill, path);
            }
            using (var font = new Font("Arial", size * 0.72f, FontStyle.Bold, GraphicsUnit.Pixel))
            using (var white = new SolidBrush(Color.White))
            {
                var fmt = new StringFormat { Alignment = StringAlignment.Center, LineAlignment = StringAlignment.Center };
                g.DrawString("P", font, white, new RectangleF(0, size * 0.04f, size, size), fmt);
            }
        }
        return bmp;
    }

    static byte[] Dib(Bitmap bmp)
    {
        int n = bmp.Width;
        int maskStride = ((n + 31) / 32) * 4;
        using (var ms = new MemoryStream())
        using (var w = new BinaryWriter(ms))
        {
            w.Write(40); w.Write(n); w.Write(n * 2); w.Write((short)1); w.Write((short)32);
            w.Write(0); w.Write(n * n * 4 + maskStride * n); w.Write(0); w.Write(0); w.Write(0); w.Write(0);
            for (int y = n - 1; y >= 0; y--)
                for (int x = 0; x < n; x++)
                {
                    Color c = bmp.GetPixel(x, y);
                    w.Write(c.B); w.Write(c.G); w.Write(c.R); w.Write(c.A);
                }
            for (int y = n - 1; y >= 0; y--)
            {
                var row = new byte[maskStride];
                for (int x = 0; x < n; x++)
                    if (bmp.GetPixel(x, y).A == 0) row[x / 8] |= (byte)(0x80 >> (x % 8));
                w.Write(row);
            }
            return ms.ToArray();
        }
    }

    public static void Write(string path)
    {
        int[] sizes = { 16, 32, 48 };
        var images = new byte[sizes.Length][];
        for (int i = 0; i < sizes.Length; i++)
            using (var b = Draw(sizes[i])) images[i] = Dib(b);
        using (var fs = File.Create(path))
        using (var w = new BinaryWriter(fs))
        {
            w.Write((short)0); w.Write((short)1); w.Write((short)sizes.Length);
            int offset = 6 + 16 * sizes.Length;
            for (int i = 0; i < sizes.Length; i++)
            {
                w.Write((byte)sizes[i]); w.Write((byte)sizes[i]); w.Write((byte)0); w.Write((byte)0);
                w.Write((short)1); w.Write((short)32); w.Write(images[i].Length); w.Write(offset);
                offset += images[i].Length;
            }
            foreach (var img in images) w.Write(img);
        }
    }
}
'@

[PokkerIcon]::Write([System.IO.Path]::GetFullPath($Out))
Write-Host "Icon written: $Out"
